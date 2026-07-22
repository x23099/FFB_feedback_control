// --- アプリケーション設定・グローバル変数 ---
const canvas = document.querySelector('#webgl-canvas');
let scene, camera, renderer;
let textMesh, starParticles, glowMesh;
const clock = new THREE.Clock();

function init() {
  // 1. シーンの作成
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x05050a, 0.0012);

  // 2. カメラの設定
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 200; // 初期位置（手前に引く）

  // 3. レンダラーの設定
  renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  // 4. 光源の設定
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);

  const pointLight = new THREE.PointLight(0x00ffff, 4, 200);
  pointLight.position.set(0, 0, 50);
  scene.add(pointLight);

  // 5. コンポーネント生成
  createStarryBackground();
  createTextMesh();

  // 6. イベントリスナー
  window.addEventListener('resize', onWindowResize);

  // 7. アニメーションの即時開始とローダーの消去
  startAnimation();
}

// 宇宙背景（星屑パーティクル）
function createStarryBackground() {
  const starsCount = 3000;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(starsCount * 3);
  const colors = new Float32Array(starsCount * 3);

  for (let i = 0; i < starsCount * 3; i += 3) {
    positions[i] = (Math.random() - 0.5) * 1000;
    positions[i + 1] = (Math.random() - 0.5) * 1000;
    positions[i + 2] = (Math.random() - 0.5) * 1000;

    colors[i] = 0.6 + Math.random() * 0.4;
    colors[i + 1] = 0.8 + Math.random() * 0.2;
    colors[i + 2] = 1.0;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // パーティクル用キャンバステクスチャ
  const pCanvas = document.createElement('canvas');
  pCanvas.width = 16;
  pCanvas.height = 16;
  const pCtx = pCanvas.getContext('2d');
  const grad = pCtx.createRadialGradient(8, 8, 0, 8, 8, 8);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  pCtx.fillStyle = grad;
  pCtx.fillRect(0, 0, 16, 16);
  const starTexture = new THREE.CanvasTexture(pCanvas);

  const material = new THREE.PointsMaterial({
    size: 2.5,
    map: starTexture,
    vertexColors: true,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  starParticles = new THREE.Points(geometry, material);
  scene.add(starParticles);
}

// 動的Canvasテクスチャによるネオン「Hello World」メッシュ生成
function createTextMesh() {
  const textCanvas = document.createElement('canvas');
  textCanvas.width = 1024;
  textCanvas.height = 256;
  const ctx = textCanvas.getContext('2d');

  // 背景透明
  ctx.clearRect(0, 0, textCanvas.width, textCanvas.height);

  // ネオン発光テキスト描画
  ctx.font = 'bold 96px "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  // グロー効果
  ctx.shadowColor = '#00ffff';
  ctx.shadowBlur = 30;
  ctx.fillStyle = '#ffffff';
  ctx.fillText('Hello World', textCanvas.width / 2, textCanvas.height / 2);

  ctx.shadowColor = '#ff00ff';
  ctx.shadowBlur = 15;
  ctx.fillText('Hello World', textCanvas.width / 2, textCanvas.height / 2);

  const texture = new THREE.CanvasTexture(textCanvas);
  texture.needsUpdate = true;

  const geometry = new THREE.PlaneGeometry(120, 30);
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide
  });

  textMesh = new THREE.Mesh(geometry, material);
  textMesh.position.set(0, 0, -200); // 遠くに配置
  scene.add(textMesh);
}

// イントロアニメーションとローダー非表示
function startAnimation() {
  const loader = document.getElementById('loader');
  
  // ローダーをフェードアウト
  gsap.to(loader, {
    opacity: 0,
    duration: 0.8,
    ease: 'power2.out',
    onComplete: () => {
      loader.style.display = 'none';

      // アニメーションタイムライン
      const tl = gsap.timeline();

      // カメラが前に進み、テキストが奥からズームイン
      tl.to(camera.position, {
        z: 70,
        duration: 3.5,
        ease: 'power2.out'
      }, 0);

      tl.to(textMesh.position, {
        z: 0,
        duration: 3.5,
        ease: 'power3.out'
      }, 0);

      tl.to(textMesh.rotation, {
        x: 0.1,
        y: 0.2,
        duration: 3.5,
        ease: 'power2.out'
      }, 0);
    }
  });

  // レンダリングループ開始
  animate();
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);

  const time = clock.getElapsedTime();

  // 背景の自転と漂い
  if (starParticles) {
    starParticles.rotation.y = time * 0.02;
    starParticles.rotation.x = time * 0.005;
  }

  // テキストのゆらめき・浮遊エフェクト
  if (textMesh) {
    textMesh.position.y = Math.sin(time * 1.5) * 2;
    textMesh.rotation.y = Math.sin(time * 0.8) * 0.05;
  }

  renderer.render(scene, camera);
}

// ドームロード完了後に初期化実行
window.addEventListener('DOMContentLoaded', init);
