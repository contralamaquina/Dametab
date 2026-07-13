const btnGrabar = document.getElementById("btnGrabar");
const btnTexto = document.getElementById("btnTexto");
const visualizador = document.getElementById("visualizador");
const estadoDiv = document.getElementById("estado");
const resultadoDiv = document.getElementById("resultado");
const cancionTitulo = document.getElementById("cancionTitulo");
const cancionArtista = document.getElementById("cancionArtista");
const listaOpciones = document.getElementById("listaOpciones");

const DURACION_GRABACION_MS = 10000; // 10 segundos

btnGrabar.addEventListener("click", iniciarFlujo);

async function iniciarFlujo() {
  resultadoDiv.classList.add("oculto");
  btnGrabar.disabled = true;

  try {
    const audioBase64 = await grabarAudio();
    mostrarEstado("Identificando la canción…");

    const cancion = await identificarCancion(audioBase64);
    if (!cancion.encontrada) {
      mostrarEstado("No pude identificar la canción. Probá de nuevo, más cerca del parlante.");
      resetearBoton();
      return;
    }

    mostrarEstado(`Encontré "${cancion.titulo}" — buscando tablatura…`);

    const tab = await buscarTablatura(cancion.titulo, cancion.artista);
    if (!tab.encontrado) {
      mostrarEstado("Identifiqué la canción, pero no encontré la tablatura. Probá buscarla manualmente.");
      resetearBoton();
      return;
    }

    mostrarResultado(cancion, tab);
    resetearBoton();
  } catch (error) {
    console.error(error);
    mostrarEstado("Hubo un error: " + error.message);
    resetearBoton();
  }
}

function resetearBoton() {
  btnGrabar.disabled = false;
  btnGrabar.classList.remove("grabando");
  btnTexto.textContent = "Escuchar";
  visualizador.classList.add("oculto");
}

function grabarAudio() {
  return new Promise(async (resolve, reject) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];

      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        btnGrabar.classList.remove("grabando");
        visualizador.classList.add("oculto");
        btnTexto.textContent = "Escuchar";

        const blob = new Blob(chunks, { type: "audio/webm" });
        const base64 = await blobABase64(blob);
        resolve(base64);
      };

      mediaRecorder.start();
      btnGrabar.classList.add("grabando");
      btnTexto.textContent = "Escuchando…";
      visualizador.classList.remove("oculto");
      mostrarEstado("Acercá el micrófono a la música 🎧");

      setTimeout(() => mediaRecorder.stop(), DURACION_GRABACION_MS);
    } catch (error) {
      reject(new Error("No pude acceder al micrófono. Revisá los permisos del navegador."));
    }
  });
}

function blobABase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function identificarCancion(audioBase64) {
  const respuesta = await fetch("/api/identificar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audio: audioBase64 }),
  });

  if (!respuesta.ok) {
    const error = await respuesta.json();
    throw new Error(error.error || "Error identificando la canción");
  }

  return respuesta.json();
}

async function buscarTablatura(titulo, artista) {
  const respuesta = await fetch("/api/buscar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, artista }),
  });

  if (!respuesta.ok) {
    const error = await respuesta.json();
    throw new Error(error.error || "Error buscando la tablatura");
  }

  return respuesta.json();
}

function mostrarEstado(texto) {
  estadoDiv.textContent = texto;
}

function mostrarResultado(cancion, tab) {
  mostrarEstado("");
  cancionTitulo.textContent = cancion.titulo;
  cancionArtista.textContent = cancion.artista;

  listaOpciones.innerHTML = "";

  tab.opciones.forEach((opcion) => {
    const tarjeta = document.createElement("div");
    tarjeta.className = "tarjeta-opcion";

    const info = document.createElement("div");
    info.className = "tarjeta-info";

    const titulo = document.createElement("p");
    titulo.className = "tarjeta-titulo";
    titulo.textContent = opcion.titulo;

    const estrellas = document.createElement("p");
    estrellas.className = "tarjeta-estrellas";
    estrellas.innerHTML =
      "♪".repeat(opcion.estrellas) +
      `<span class="cuerda-apagada">${"♪".repeat(5 - opcion.estrellas)}</span>`;

    info.appendChild(titulo);
    info.appendChild(estrellas);

    const boton = document.createElement("a");
    boton.href = opcion.url;
    boton.target = "_blank";
    boton.rel = "noopener noreferrer";
    boton.className = "boton-tab";
    boton.textContent = "Abrir →";

    tarjeta.appendChild(info);
    tarjeta.appendChild(boton);
    listaOpciones.appendChild(tarjeta);
  });

  resultadoDiv.classList.remove("oculto");
}
