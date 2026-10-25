import * as THREE from "https://unpkg.com/three@0.170.0/build/three.module.js";

const REDUZ = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const ROXO = 0x660e9c;
const ESCURO = 0x470a6d;
const VERMELHO = 0xd21f1f;
const AZUL = 0x1f4eae;

const canvas = document.querySelector("canvas[data-cena]");
if (canvas) iniciar(canvas);

function iniciar(alvo) {
  const nome = alvo.dataset.cena || "estimativa";
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: alvo, antialias: true, alpha: true });
  } catch (erro) {
    alvo.dataset.estado = "erro";
    console.error(erro);
    return;
  }
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const cena = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
  camera.position.set(0, 4.2, 10);
  camera.lookAt(0, 0, 0);
  cena.add(new THREE.AmbientLight(0xffffff, 0.72));
  const luz = new THREE.DirectionalLight(0xffffff, 1.2);
  luz.position.set(4, 8, 6);
  cena.add(luz);

  const grupo = new THREE.Group();
  grupo.userData.nome = nome;
  cena.add(grupo);

  const api = {
    definirCobertura() {},
    definirPesos() {},
  };
  if (nome === "estimativa") montarEstimativa(grupo, api);
  else if (nome === "mapa") montarOnda(grupo);
  else if (nome === "deputados") montarColunas(grupo);
  else if (nome === "metodo") montarNuvem(grupo);
  else montarSecoes(grupo, api);

  let quadros = 0;
  let quadroId = 0;

  function ajustar() {
    const w = alvo.clientWidth || 640;
    const h = alvo.clientHeight || 256;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  ajustar();
  const obs = new ResizeObserver(ajustar);
  obs.observe(alvo.parentElement || alvo);

  function tick(agora) {
    quadros += 1;
    alvo.dataset.quadros = String(quadros);
    const t = agora / 1000;
    if (nome === "estimativa") animarEstimativa(grupo, t);
    else if (nome === "mapa") aplicar(grupo.userData.onda, t);
    else if (nome === "deputados") grupo.rotation.y = t * 0.18;
    else if (nome === "metodo") grupo.rotation.y = t * 0.22;
    else animarSecoes(grupo, t);
    renderer.render(cena, camera);
    if (!REDUZ) quadroId = requestAnimationFrame(tick);
  }

  try {
    tick(performance.now());
    alvo.dataset.estado = "ok";
  } catch (erro) {
    alvo.dataset.estado = "erro";
    console.error(erro);
    return;
  }

  window.__cena = api;
  window.dispatchEvent(new Event("cena-pronta"));
  window.addEventListener("pagehide", () => {
    cancelAnimationFrame(quadroId);
    obs.disconnect();
    renderer.dispose();
  }, { once: true });
}

function grade(nx, nz, material, altura) {
  const geo = new THREE.BoxGeometry(0.36, 1, 0.36);
  const mesh = new THREE.InstancedMesh(geo, material, nx * nz);
  mesh.userData = { nx, nz, altura, dummy: new THREE.Object3D() };
  aplicar(mesh, 0);
  return mesh;
}

function aplicar(mesh, t) {
  const { nx, nz, altura, dummy } = mesh.userData;
  let i = 0;
  for (let x = 0; x < nx; x += 1) {
    for (let z = 0; z < nz; z += 1) {
      const h = Math.max(0.02, altura(x, z, t));
      dummy.position.set((x - (nx - 1) / 2) * 0.46, h / 2, (z - (nz - 1) / 2) * 0.46);
      dummy.scale.set(1, h, 1);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      i += 1;
    }
  }
  mesh.instanceMatrix.needsUpdate = true;
  mesh.computeBoundingSphere();
}

function materialSolido(cor) {
  return new THREE.MeshStandardMaterial({ color: cor, roughness: 0.55, metalness: 0 });
}

function montarEstimativa(grupo, api) {
  const clara = grade(4, 4, materialSolido(VERMELHO), () => 1.6);
  const escura = grade(4, 4, materialSolido(AZUL), () => 1.7);
  clara.position.x = -1.6;
  escura.position.x = 1.6;
  grupo.add(clara, escura);
  grupo.userData.partes = [clara, escura];
  grupo.userData.pesos = { lula: 0.4904, flavio: 0.5096 };
  api.definirPesos = (flavio, lula) => {
    grupo.userData.pesos = {
      flavio: Number(flavio) || 0,
      lula: Number(lula) || 0,
    };
  };
}

function animarEstimativa(grupo, t) {
  const { lula, flavio } = grupo.userData.pesos;
  const [clara, escura] = grupo.userData.partes;
  clara.userData.altura = (x, z, tempo) => 0.35 + lula * 3.3 + Math.sin(tempo * 1.5 + x + z) * 0.07;
  escura.userData.altura = (x, z, tempo) => 0.35 + flavio * 3.3 + Math.sin(tempo * 1.5 + x) * 0.07;
  aplicar(clara, t);
  aplicar(escura, t);
  grupo.rotation.y = Math.sin(t * 0.35) * 0.4;
}

function montarOnda(grupo) {
  const mesh = grade(16, 16, materialSolido(ROXO), (x, z, t) => (
    0.2 + Math.max(0, Math.sin(x * 0.55 + t * 1.3) * Math.cos(z * 0.42 + t * 0.8)) * 1.7
  ));
  grupo.add(mesh);
  grupo.userData.onda = mesh;
}

function montarColunas(grupo) {
  const mesh = grade(9, 9, materialSolido(ESCURO), (x, z) => 0.25 + ((x * 5 + z * 3) % 6) * 0.28);
  grupo.add(mesh);
}

function montarNuvem(grupo) {
  const n = 380;
  const pos = new Float32Array(n * 3);
  const aleatorio = semente();
  for (let i = 0; i < n; i += 1) {
    const u = Math.max(aleatorio(), 1e-6);
    const v = aleatorio();
    const g = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    pos[i * 3] = g * 1.45;
    pos[i * 3 + 1] = (aleatorio() - 0.5) * 1.5;
    pos[i * 3 + 2] = (aleatorio() - 0.5) * 1.5;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  grupo.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: ROXO, size: 0.075 })));
  const eixo = new THREE.Mesh(
    new THREE.BoxGeometry(0.045, 2.4, 0.045),
    materialSolido(ESCURO),
  );
  grupo.add(eixo);
}

function montarSecoes(grupo, api) {
  const nx = 16;
  const nz = 8;
  const fio = new THREE.MeshBasicMaterial({
    color: ESCURO,
    wireframe: true,
    transparent: true,
    opacity: 0.55,
  });
  const cheios = grade(nx, nz, materialSolido(ROXO), () => 0.02);
  const vazios = grade(nx, nz, fio, () => 0.62);
  grupo.add(vazios, cheios);
  grupo.userData.secoes = { cheios, vazios, nx, nz, total: nx * nz, fracao: 0, fio };
  api.definirCobertura = (fracao) => {
    grupo.userData.secoes.fracao = Math.min(1, Math.max(0, Number(fracao) || 0));
  };
}

function animarSecoes(grupo, t) {
  const s = grupo.userData.secoes;
  const limite = Math.round(s.fracao * s.total);
  const dummyC = s.cheios.userData.dummy;
  const dummyV = s.vazios.userData.dummy;
  let i = 0;
  for (let x = 0; x < s.nx; x += 1) {
    for (let z = 0; z < s.nz; z += 1) {
      const cheio = i < limite;
      const hC = cheio ? 0.85 : 0.02;
      const hV = cheio ? 0.02 : 0.5 + Math.sin(t * 2 + x * 0.4 + z) * 0.06;
      poser(dummyC, s.nx, s.nz, x, z, hC);
      s.cheios.setMatrixAt(i, dummyC.matrix);
      poser(dummyV, s.nx, s.nz, x, z, hV);
      s.vazios.setMatrixAt(i, dummyV.matrix);
      i += 1;
    }
  }
  s.cheios.instanceMatrix.needsUpdate = true;
  s.vazios.instanceMatrix.needsUpdate = true;
  s.fio.opacity = 0.35 + Math.sin(t * 2) * 0.2;
  grupo.rotation.y = Math.sin(t * 0.3) * 0.35;
}

function poser(dummy, nx, nz, x, z, h) {
  dummy.position.set((x - (nx - 1) / 2) * 0.46, h / 2, (z - (nz - 1) / 2) * 0.46);
  dummy.scale.set(1, h, 1);
  dummy.rotation.set(0, 0, 0);
  dummy.updateMatrix();
}

function semente() {
  let a = 0x5eed;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
