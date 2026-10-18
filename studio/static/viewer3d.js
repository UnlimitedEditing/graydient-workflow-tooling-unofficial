import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export class StudioViewer3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.transformControls = null;
    this.assets = [];          // Array of { id, name, object, type }
    this.selectedAsset = null;
    this.currentModel = null;
    this.animId = null;

    this.init();
  }

  init() {
    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 450;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0e17);

    // PBR Environment & Grid
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    const grid = new THREE.GridHelper(10, 20, 0x00f2fe, 0x1e293b);
    grid.position.y = -0.01;
    this.scene.add(grid);

    // Lights
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x1e293b, 1.2);
    this.scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(5, 10, 7);
    this.scene.add(dirLight);

    // Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);
    this.camera.position.set(0, 1.5, 3.5);

    // Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.target.set(0, 0.5, 0);

    // Transform Controls (Move / Rotate / Scale Gizmo)
    this.transformControls = new TransformControls(this.camera, this.renderer.domElement);
    this.transformControls.size = 0.75;
    this.transformControls.addEventListener('dragging-changed', (e) => {
      this.controls.enabled = !e.value;
    });
    this.scene.add(this.transformControls);

    // Keyboard shortcuts for gizmo (W=Translate, E=Rotate, R=Scale)
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.key === 'w' || e.key === 'W') this.setGizmoMode('translate');
      if (e.key === 'e' || e.key === 'E') this.setGizmoMode('rotate');
      if (e.key === 'r' || e.key === 'R') this.setGizmoMode('scale');
    });

    // Resize listener
    window.addEventListener('resize', () => this.onResize());

    // Animation Loop
    this.animate();
  }

  setGizmoMode(mode) {
    if (this.transformControls) {
      this.transformControls.setMode(mode);
    }
  }

  addGLBToScene(url, name = 'Asset', onProgress, onError) {
    const loader = new GLTFLoader();
    loader.load(
      url,
      (gltf) => {
        const obj = gltf.scene;
        const id = 'asset_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4);
        obj.userData.assetId = id;
        this.scene.add(obj);

        const assetEntry = { id, name, object: obj, type: 'glb' };
        this.assets.push(assetEntry);
        this.selectAsset(id);
        if (this.assets.length === 1) {
          this.frameObject(obj);
        }
        if (onProgress) onProgress(100, assetEntry);
      },
      (xhr) => {
        if (onProgress && xhr.total) {
          onProgress(Math.round((xhr.loaded / xhr.total) * 100));
        }
      },
      onError
    );
  }

  selectAsset(id) {
    const asset = this.assets.find(a => a.id === id);
    if (asset) {
      this.selectedAsset = asset;
      this.transformControls.attach(asset.object);
    } else {
      this.selectedAsset = null;
      this.transformControls.detach();
    }
  }

  deleteSelectedAsset() {
    if (!this.selectedAsset) return;
    this.transformControls.detach();
    this.scene.remove(this.selectedAsset.object);
    this.assets = this.assets.filter(a => a.id !== this.selectedAsset.id);
    this.selectedAsset = null;
  }

  exportCombinedScene(filename = 'staged_environment.glb') {
    const exporter = new GLTFExporter();
    const exportGroup = new THREE.Group();
    this.assets.forEach(a => {
      exportGroup.add(a.object.clone());
    });

    exporter.parse(
      exportGroup,
      (gltf) => {
        const blob = new Blob([gltf], { type: 'model/gltf-binary' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
      },
      (error) => {
        console.error('GLTF Export error:', error);
      },
      { binary: true }
    );
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    if (width === 0 || height === 0) return;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    this.animId = requestAnimationFrame(() => this.animate());
    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  loadGLB(url, onProgress, onError) {
    this.clearModel();
    this.addGLBToScene(url, 'Primary Mesh', onProgress, onError);
  }

  loadPLY(url, onProgress, onError) {
    this.clearModel();
    const loader = new PLYLoader();
    loader.load(
      url,
      (geometry) => {
        geometry.computeVertexNormals();
        let material;
        if (geometry.hasAttribute('color')) {
          material = new THREE.PointsMaterial({ size: 0.015, vertexColors: true });
        } else {
          material = new THREE.PointsMaterial({ size: 0.015, color: 0x00f2fe });
        }
        this.currentModel = new THREE.Points(geometry, material);
        this.scene.add(this.currentModel);
        this.frameObject(this.currentModel);
        if (onProgress) onProgress(100);
      },
      (xhr) => {
        if (onProgress && xhr.total) {
          onProgress(Math.round((xhr.loaded / xhr.total) * 100));
        }
      },
      (err) => {
        console.error('Error loading PLY:', err);
        if (onError) onError(err);
      }
    );
  }

  frameObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    // Center model at origin on grid
    object.position.x += object.position.x - center.x;
    object.position.y += object.position.y - box.min.y;
    object.position.z += object.position.z - center.z;

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = this.camera.fov * (Math.PI / 180);
    let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 1.5;
    cameraZ = Math.max(cameraZ, 1.5);

    this.camera.position.set(cameraZ * 0.7, cameraZ * 0.6, cameraZ);
    this.controls.target.set(0, size.y / 2, 0);
    this.camera.lookAt(0, size.y / 2, 0);
    this.controls.update();
  }

  clearModel() {
    if (this.transformControls) this.transformControls.detach();
    this.assets.forEach(a => this.scene.remove(a.object));
    this.assets = [];
    this.selectedAsset = null;
    if (this.currentModel) {
      this.scene.remove(this.currentModel);
      this.currentModel = null;
    }
  }

  toggleWireframe(enabled) {
    if (!this.currentModel) return;
    this.currentModel.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material.wireframe = enabled;
      }
    });
  }
}
