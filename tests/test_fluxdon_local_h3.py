"""CPU-only contract tests; these do not replace a real ComfyUI/GPU render."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fluxdon_nodes", ROOT / "fluxdon-local-h3/nodes.py")
nodes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nodes)
sys.path.insert(0, str(ROOT))
from templates import gen_minimax_h3_partner_equivalents as gen


class Core:
    class MiniMaxH3ImageToVideo:
        @staticmethod
        def execute(**kw):
            return (('conditioning', kw), 'latent')
    class MiniMaxH3ReferenceToVideo:
        @staticmethod
        def execute(**kw):
            return (('reference', kw), 'latent')
    class MiniMaxH3AddGuide:
        @staticmethod
        def execute(**kw):
            return (('guide', kw),)


class LocalNodeTests(unittest.TestCase):
    def setUp(self):
        self.h3 = mock.patch.object(nodes, '_h3', return_value=Core)
        self.h3.start()
        self.addCleanup(self.h3.stop)
        self.common = dict(clip='clip', vae='vae', prompt='prompt', width=1024, height=576, length=124)

    def test_recast_references_and_optional_identity(self):
        out = nodes.FluxdonH3Recast().prepare(**self.common, audio_vae='av', identity='id',
             identity_2='id2', source_frames='video', source_audio='sound')
        kw = out[0][1]
        self.assertEqual(kw['ref_images'], {'ref_image_0': 'id', 'ref_image_1': 'id2'})
        self.assertEqual(kw['ref_videos'], {'ref_video_0': 'video'})
        self.assertEqual(kw['ref_video_audios'], {'ref_video_audio_0': 'sound'})
        out = nodes.FluxdonH3Recast().prepare(**self.common, audio_vae='av', identity='id', source_frames='video')
        self.assertEqual(out[0][1]['ref_images'], {'ref_image_0': 'id'})
        self.assertEqual(out[0][1]['ref_video_audios'], {})

    def test_extend_and_insert_pass_context_and_return_all_metadata(self):
        for cls, frame in ((nodes.FluxdonH3Extend, 0), (nodes.FluxdonH3Insert, 51)):
            with self.subTest(cls=cls), mock.patch.object(nodes, '_context', return_value=('masked', 39, frame, 39)) as ctx:
                out = cls().prepare(**self.common, audio_vae='av', source_frames='frames', source_audio='audio',
                                    source_fps=24.0, context_length=39, crop='center', audio_feather_ticks=8, insert_frame=frame)
                self.assertEqual(out[1:], ('masked', 39, frame, 39))
                self.assertEqual(ctx.call_args.kwargs['latent'], 'latent')
                self.assertEqual(ctx.call_args.kwargs['insert_frame'], frame)

    def test_missing_context_has_actionable_error(self):
        with mock.patch.dict(sys.modules, {'nodes': types.SimpleNamespace(NODE_CLASS_MAPPINGS={})}):
            with self.assertRaisesRegex(RuntimeError, 'Motion-Context'):
                nodes._context()

    def test_reframe_adds_video_and_audio_guide(self):
        out = nodes.FluxdonH3Reframe().prepare(**self.common, audio_vae='av', guide_frames='frames', source_audio='audio')
        self.assertEqual(out[0][1]['image'], 'frames')
        self.assertEqual(out[0][1]['audio'], 'audio')
        self.assertEqual(out[1], 'latent')

    def test_lipsync_uses_portrait_and_audio(self):
        out = nodes.FluxdonH3LipSync().prepare(**self.common, audio_vae='av', portrait='portrait', speech='voice')
        guide = out[0][1]
        self.assertEqual(guide['audio'], 'voice')
        self.assertEqual(guide['positive'][1]['first_frame'], 'portrait')

    def test_camera_includes_user_controls(self):
        out = nodes.FluxdonH3CameraControl().prepare(**self.common, first_frame='image', azimuth=25, elevation=-10, dolly=1.5)
        kw = out[0][1]
        self.assertIn('orbit 25 degrees', kw['prompt'])
        self.assertIn('-10 degrees', kw['prompt'])
        self.assertIn('1.5x', kw['prompt'])
        self.assertEqual(kw['first_frame'], 'image')

    def test_generated_graphs_match_node_contracts_and_mappings(self):
        for slug, builder in gen.TASKS.items():
            with self.subTest(slug=slug):
                graph, fields, _ = builder()
                fields = gen.use_local_task_node(slug, graph, fields)
                api = graph.to_api()
                local = api['210']
                cls = nodes.NODE_CLASS_MAPPINGS[local['class_type']]
                schema = cls.INPUT_TYPES()
                required, optional = schema['required'], schema.get('optional', {})
                self.assertEqual(set(local['inputs']) - set(required) - set(optional), set())
                self.assertEqual(set(required) - set(local['inputs']), set())
                std = graph.to_standard()
                self.assertEqual(gen.verify(graph, std, api), [])
                wf = gen.GraydientWorkflow(name=slug)
                wf.set_workflows(std, api)
                gen.add_concepts(wf, graph)
                gen.add_fields(wf, graph, fields)
                self.assertEqual(len(wf.concept_mapping), 10)
                fm = wf.to_dict()['graydient_workflow']['field_mapping']
                self.assertEqual(len(fm), len({f['local_field'] for f in fm}))
                for f in fm:
                    node = next(n for n in std['nodes'] if n['id'] == f['node_id'])
                    self.assertLess(f['node_input_index'], len(node['widgets_values']))
                for n in api.values():
                    for value in n['inputs'].values():
                        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                            source_cls = api[value[0]]['class_type']
                            if source_cls in nodes.NODE_CLASS_MAPPINGS:
                                self.assertLess(value[1], len(nodes.NODE_CLASS_MAPPINGS[source_cls].RETURN_TYPES))

    def test_backups_reference_uploaded_pack(self):
        for slug in gen.TASKS:
            path = ROOT / 'workflows/minimax-h3-partner-equivalents' / f'GraydientWorkflow-minimax-h3-{slug}-v1.json'
            d = json.loads(path.read_text())['graydient_workflow']
            self.assertIn('https://github.com/UnlimitedEditing/fluxdon-local-h3', d['requirements']['github'])
            self.assertEqual(d['requirements']['pip'], [])
            self.assertEqual(set(d['requirements']['github']), set(gen.GITHUB_REQUIREMENTS))
            api = json.loads(d['workflow_2'])
            standard = json.loads(d['workflow'])
            self.assertEqual(uuid.UUID(standard['id']).version, 5)
            self.assertEqual(api['210']['class_type'], gen.LOCAL_CLASSES[slug])
            self.assertFalse(any('Hailuo03Max' in n['class_type'] for n in api.values()))
            self.assertEqual(len(d['concept_mapping']), 10)
            concepts = d['concept_mapping']
            for nid, widget, folder, filename in (
                (128, 'clip_name', 'text_encoders', gen.CLIP),
                (120, 'vae_name', 'vae', gen.VAE_AUDIO),
                (119, 'vae_name', 'vae', gen.VAE_VIDEO),
                (317, 'lora_name', 'loras', gen.LORA_TAOMATE),
                (127, 'unet_name', 'diffusion_models', gen.UNET),
            ):
                self.assertEqual(api[str(nid)]['inputs'][widget], filename)
                matches = [c for c in concepts if c['destination'] == f'{folder}/{filename}']
                self.assertEqual(len(matches), 1)
                self.assertTrue(matches[0]['field_mapping'].startswith(f'{nid}-'))
                self.assertTrue(matches[0]['field_mapping'].endswith(f'-{widget}'))
            for i, (name_index, strength_index) in gen.LORA_SLOT_SUFFIX.items():
                name = f'171-EasyLoraStack.{name_index}-lora_{i}_name'
                weight = f'171-EasyLoraStack.{strength_index}-lora_{i}_strength'
                concept = next(c for c in concepts if c['field_mapping'] == name)
                self.assertEqual(concept['weight_field_mapping'], weight)
                self.assertTrue(concept['allow_dynamic'])
                self.assertEqual(concept['dynamic_family'], 'H3')
            self.assertEqual(api['148']['class_type'], 'SaveVideo')


if __name__ == '__main__':
    unittest.main()
