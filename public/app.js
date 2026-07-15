const btnGrabar = document.getElementById("btnGrabar");
const btnTexto = document.getElementById("btnTexto");
const visualizador = document.getElementById("visualizador");
const ondas = document.getElementById("ondas");
const vinilo = document.getElementById("vinilo");
const estadoDiv = document.getElementById("estado");
const resultadoDiv = document.getElementById("resultado");
const cancionTitulo = document.getElementById("cancionTitulo");
const cancionArtista = document.getElementById("cancionArtista");
const listaOpciones = document.getElementById("listaOpciones");
const portadaAlbum = document.getElementById("portadaAlbum");
const btnNuevaBusqueda = document.getElementById("btnNuevaBusqueda");

// --- elementos del formulario manual (fallback cuando no se identifica) ---
const busquedaManual = document.getElementById("busquedaManual");
const formBusquedaManual = document.getElementById("formBusquedaManual");
const inputArtistaManual = document.getElementById("inputArtistaManual");
const inputTituloManual = document.getElementById("inputTituloManual");
const btnCancelarManual = document.getElementById("btnCancelarManual");

const DURACION_GRABACION_MS = 10000; // 10 segundos

// Registrar el service worker (necesario para que el navegador
// considere la app instalable como PWA)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.warn("No se pudo registrar el service worker:", error);
    });
  });
}

btnGrabar.addEventListener("click", iniciarFlujo);
btnNuevaBusqueda.addEventListener("click", reiniciar);

if (formBusquedaManual) {
  formBusquedaManual.addEventListener("submit", manejarBusquedaManual);
}
if (btnCancelarManual) {
  btnCancelarManual.addEventListener("click", () => {
    ocultarBusquedaManual();
    resetearBoton();
  });
}

async function iniciarFlujo() {
  resultadoDiv.classList.add("oculto");
  ocultarBusquedaManual();
  btnGrabar.disabled = true;

  try {
    const audioBase64 = await grabarAudio();

    mostrarEstadoProcesando("Identificando la canción…");
    const cancion = await identificarCancion(audioBase64);

    if (!cancion.encontrada) {
      // Ni AudD ni ACRCloud reconocieron la canción: le preguntamos
      // al usuario el artista/título a mano en vez de rendirnos.
      ocultarVinilo();
      mostrarEstado("No pude identificar la canción por el audio. ¿La buscamos por nombre?");
      mostrarBusquedaManual();
      resetearBoton();
      return;
    }

    mostrarEstadoProcesando(`Encontré "${cancion.titulo}" — buscando tablatura…`);
    const tab = await buscarTablatura(cancion.titulo, cancion.artista);

    ocultarVinilo();
    mostrarResultado(cancion, tab);
    resetearBoton();
  } catch (error) {
    console.error(error);
    ocultarVinilo();
    mostrarEstado("Hubo un error: " + error.message);
    resetearBoton();
  }
}

async function manejarBusquedaManual(evento) {
  evento.preventDefault();

  const artista = inputArtistaManual.value.trim();
  const titulo = inputTituloManual.value.trim();

  if (!artista && !titulo) {
    mostrarEstado("Escribí al menos el artista o el título de la canción.");
    return;
  }

  ocultarBusquedaManual();
  mostrarEstadoProcesando("Buscando tablatura…");

  try {
    // Serper (Google) corrige automáticamente errores de tipeo comunes,
    // así que no hace falta "limpiar" lo que escribió el usuario: se
    // manda tal cual y el buscador se encarga de interpretarlo.
    const tab = await buscarTablatura(
      titulo || "(sin título)",
      artista || "(sin artista)",
      true
    );

    ocultarVinilo();
    mostrarResultado(
      {
        titulo: titulo || "Búsqueda manual",
        artista: artista || "",
        portada: null,
      },
      tab
    );
    resetearBoton();
  } catch (error) {
    console.error(error);
    ocultarVinilo();
    mostrarEstado("Hubo un error buscando la tablatura: " + error.message);
    resetearBoton();
  }
}

function mostrarBusquedaManual() {
  if (!busquedaManual) return;
  inputArtistaManual.value = "";
  inputTituloManual.value = "";
  busquedaManual.classList.remove("oculto");
  inputTituloManual.focus();
}

function ocultarBusquedaManual() {
  if (!busquedaManual) return;
  busquedaManual.classList.add("oculto");
}

function mostrarEstadoProcesando(texto) {
  mostrarEstado(texto);
  estadoDiv.classList.remove("escuchando");
  vinilo.classList.remove("oculto");
}

function ocultarVinilo() {
  vinilo.classList.add("oculto");
}

function resetearBoton() {
  btnGrabar.disabled = false;
  btnGrabar.classList.remove("grabando");
  btnTexto.textContent = "Escuchar";
  visualizador.classList.add("oculto");
  ondas.classList.add("oculto");
  vinilo.classList.add("oculto");
  estadoDiv.classList.remove("escuchando");
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
        ondas.classList.add("oculto");
        btnTexto.textContent = "Escuchar";

        const blob = new Blob(chunks, { type: "audio/webm" });
        const base64 = await blobABase64(blob);
        resolve(base64);
      };

      mediaRecorder.start();
      btnGrabar.classList.add("grabando");
      btnTexto.textContent = "Escuchando…";
      visualizador.classList.remove("oculto");
      ondas.classList.remove("oculto");
      mostrarEstado("Acercá el micrófono a la música 🎧");
      estadoDiv.classList.add("escuchando");

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

async function buscarTablatura(titulo, artista, esBusquedaManual = false) {
  const respuesta = await fetch("/api/buscar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, artista, manual: esBusquedaManual }),
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

function extraerDominio(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return host;
  } catch {
    return url;
  }
}

function reiniciar() {
  resultadoDiv.classList.add("oculto");
  ocultarBusquedaManual();
  listaOpciones.innerHTML = "";
  portadaAlbum.classList.add("oculto");
  portadaAlbum.removeAttribute("src");
  mostrarEstado("");
  estadoDiv.classList.remove("escuchando");
  btnGrabar.disabled = false;
  visualizador.classList.add("oculto");
  ondas.classList.add("oculto");
  vinilo.classList.add("oculto");
  // Llevamos el scroll arriba del todo para que quede como "recién entrado"
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function mostrarResultado(cancion, tab) {
  mostrarEstado("");
  cancionTitulo.textContent = cancion.titulo;
  cancionArtista.textContent = cancion.artista;

  if (cancion.portada) {
    portadaAlbum.src = cancion.portada;
    portadaAlbum.classList.remove("oculto");
  } else {
    portadaAlbum.classList.add("oculto");
    portadaAlbum.removeAttribute("src");
  }

  listaOpciones.innerHTML = "";

  if (!tab.encontrado) {
    mostrarSinTablatura(cancion);
    resultadoDiv.classList.remove("oculto");
    return;
  }

  tab.opciones.forEach((opcion) => {
    const tarjeta = document.createElement("div");
    tarjeta.className = "tarjeta-opcion";

    const info = document.createElement("div");
    info.className = "tarjeta-info";

    const dominio = document.createElement("span");
    dominio.className = "tarjeta-dominio";
    dominio.textContent = extraerDominio(opcion.url);

    const titulo = document.createElement("p");
    titulo.className = "tarjeta-titulo";
    titulo.textContent = opcion.titulo;

    const estrellas = document.createElement("p");
    estrellas.className = "tarjeta-estrellas";
    estrellas.innerHTML =
      "♪".repeat(opcion.estrellas) +
      `<span class="cuerda-apagada">${"♪".repeat(5 - opcion.estrellas)}</span>`;

    info.appendChild(dominio);
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

function mostrarSinTablatura(cancion) {
  const aviso = document.createElement("p");
  aviso.className = "tarjeta-titulo";
  aviso.textContent = "No encontramos la tablatura automáticamente, pero podés buscarla manualmente:";

  const consulta = encodeURIComponent(`${cancion.titulo} ${cancion.artista} acordes`);
  const boton = document.createElement("a");
  boton.href = `https://www.google.com/search?q=${consulta}`;
  boton.target = "_blank";
  boton.rel = "noopener noreferrer";
  boton.className = "boton-tab";
  boton.textContent = "Buscar en Google →";

  const tarjeta = document.createElement("div");
  tarjeta.className = "tarjeta-opcion";
  tarjeta.appendChild(aviso);
  tarjeta.appendChild(boton);

  listaOpciones.appendChild(tarjeta);
}
