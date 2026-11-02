"""
Shared helpers for the two MiniMax H3 chained builds (gen_h3_ref_draft.py, gen_h3_regen2k.py).

One node table -> BOTH the API/prompt graph and the standard/UI graph, so the two cannot drift
(COMFYUI-REFERENCE sec 1). A node spec is a dict:

    id, type, title, pos, size
    inputs   : {api_name: literal | [src_id, src_slot]}   (a list value is a LINK, anything else a widget)
    widgets  : ordered API widget names as the frontend serialises them into `widgets_values`
               (include 'control_after_generate' after a seed widget; it has no API counterpart)
    wdefault : {widget_name: value} used in `widgets_values` when that widget is LINKED in the API graph
    outputs  : [(name, type), ...] in slot order

Widget / output tables here come from the node sources read on 2026-11-02 (see each gen_* docstring),
not from memory.
"""

import json

SEED_LIKE = ("seed", "noise_seed")


def build_api(nodes):
    api = {}
    for n in nodes:
        if n["type"] in ("Note", "MarkdownNote"):
            continue  # UI-only: must never reach the API graph
        api[str(n["id"])] = {
            "class_type": n["type"],
            "inputs": dict(n["inputs"]),
            "_meta": {"title": n["title"]},
        }
    return api


def build_standard(nodes, groups, note_text=None):
    by_id = {n["id"]: n for n in nodes}
    std_nodes, links, link_id = [], [], 0
    for order, n in enumerate(nodes):
        node_inputs, widget_values = [], []
        for name in n.get("widgets", []):
            if name == "control_after_generate":
                widget_values.append("fixed")
                continue
            val = n["inputs"].get(name, n.get("wdefault", {}).get(name))
            if isinstance(n["inputs"].get(name), list):
                val = n.get("wdefault", {}).get(name)
            widget_values.append(val)
        for name, val in n["inputs"].items():
            if not isinstance(val, list):
                continue
            src_id, src_slot = val
            src_type = by_id[src_id]["outputs"][src_slot][1]
            link_id += 1
            entry = {"name": name, "type": src_type, "link": link_id}
            if name in n.get("widgets", []):
                entry["widget"] = {"name": name}
            links.append([link_id, src_id, src_slot, n["id"], len(node_inputs), src_type])
            node_inputs.append(entry)
        std_nodes.append({
            "id": n["id"], "type": n["type"], "pos": n["pos"], "size": n["size"], "flags": {},
            "order": order, "mode": 0, "inputs": node_inputs,
            "outputs": [{"name": o[0], "type": o[1], "links": [], "slot_index": i}
                        for i, o in enumerate(n["outputs"])],
            "title": n["title"], "properties": {"Node name for S&R": n["type"]},
            "widgets_values": widget_values,
        })
    # Second pass: back-fill producer `links` (STD_OUTPUT_LINK_BACKREF_MISSING, KI harvest 2026-11-01).
    sid = {n["id"]: n for n in std_nodes}
    for lid, src, slot, *_ in links:
        sid[src]["outputs"][slot]["links"].append(lid)
    if note_text:
        nid = max(n["id"] for n in nodes) + 1
        std_nodes.append({"id": nid, "type": "Note", "pos": [30, -260], "size": [760, 220], "flags": {},
                          "order": 99, "mode": 0, "inputs": [], "outputs": [], "properties": {},
                          "widgets_values": [note_text], "color": "#232b3c", "bgcolor": "#343b4d"})
    return {
        "last_node_id": max(n["id"] for n in std_nodes),
        "last_link_id": link_id,
        "nodes": std_nodes,
        "links": links,
        "groups": [{"id": i + 1, "title": t, "bounding": b, "color": c, "font_size": 22, "flags": {}}
                   for i, (t, b, c) in enumerate(groups)],
        "config": {},
        "extra": {"ds": {"scale": 0.6, "offset": [60, 300]}},
        "version": 0.4,
    }


def fm(local_field, node_id, node_input_name, node_input_index, node_name,
       default_value=None, minimum_value=None, maximum_value=None, help_text=""):
    """Graydient stores field_mapping values as strings (KI-007 sec 44)."""
    s = lambda v: None if v is None else str(v)
    return {"default_value": s(default_value), "help_text": help_text, "local_field": local_field,
            "maximum_value": s(maximum_value), "minimum_value": s(minimum_value), "node_id": node_id,
            "node_input_index": node_input_index, "node_input_name": node_input_name,
            "node_name": node_name}


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[WROTE] {path}")


FLAGS_OFF = {
    "supports_txt2img": False, "supports_img2img": False, "supports_txt2vid": False,
    "supports_img2vid": False, "supports_vid2img": False, "supports_vid2vid": False,
    "supports_txt2wav": False, "supports_vid2wav": False, "supports_wav2txt": False,
    "supports_low_memory": False, "supports_dynamic_concepts": False,
    "install_detected_nodes": True, "split_prompt_pos_neg": False, "is_public": False,
    "is_deleted": False, "image_url": None, "external_config": None, "external_provider": None,
    "extra_data": None, "max_collect_attempts": None, "pre_install_script": None,
    "post_install_script": None, "platform": "comfyui", "version": 1,
}
