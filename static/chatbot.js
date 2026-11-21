(() => {
  const root = document.querySelector('.hotel-chat');
  if (!root) return;

  const launcher = root.querySelector('.hotel-chat__launcher');
  const panel = root.querySelector('.hotel-chat__panel');
  const closeButton = root.querySelector('.hotel-chat__close');
  const messages = root.querySelector('.hotel-chat__messages');
  const form = root.querySelector('.hotel-chat__form');
  const input = root.querySelector('#hotel-chat-input');

  const openChat = (open) => {
    panel.hidden = !open;
    launcher.setAttribute('aria-expanded', String(open));
    if (open) input.focus();
    else launcher.focus();
  };

  launcher.addEventListener('click', () => openChat(panel.hidden));
  closeButton.addEventListener('click', () => openChat(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) openChat(false);
  });

  const addBubble = (text, who) => {
    const bubble = document.createElement('div');
    bubble.className = `hotel-chat__bubble hotel-chat__bubble--${who}`;
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  };

  const answerFor = (question) => {
    const q = question.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    if (/hola|buenas|buenos dias|buenas tardes/.test(q)) return '¡Hola! 😊 Dime qué información necesitas sobre tu estancia y con gusto te orientaré.';
    if (/reserv|habitacion|cuarto|disponib/.test(q)) return 'Para reservar, entra a “Habitaciones”, elige una opción y abre “Consultar disponibilidad”. Selecciona entrada y salida; la fecha de salida debe ser posterior a la de entrada. Después sigue los pasos para confirmar.';
    if (/promoc|descuent|oferta/.test(q)) return 'En Promociones encontrarás habitaciones destacadas con 15% de descuento sobre la tarifa por noche. Elige tus fechas para consultar las opciones disponibles.';
    if (/pag|tarjeta|cobro/.test(q)) return 'Al completar una reserva, sigue el enlace de pago y revisa el monto mostrado antes de continuar. No compartas aquí datos de tarjeta ni contraseñas.';
    if (/cancel|modific|cambiar fecha/.test(q)) return 'No puedo modificar ni cancelar reservas desde este chat. Consulta con recepción para que revisen tu caso.';
    if (/ubic|donde|direccion|llegar/.test(q)) return 'La información del hotel muestra su ubicación en Cancún, Quintana Roo. En el detalle de cada habitación puedes consultar el mapa.';
    if (/check.?in|entrada|llegada|salida|check.?out/.test(q)) return 'Puedes elegir las fechas de entrada y salida al consultar una habitación. Para horarios de llegada o salida, confirma directamente con recepción.';
    if (/contact|persona|recepcion|ayuda|problema/.test(q)) return 'Para una situación específica que requiera atención del equipo, comunícate directamente con recepción. Este asistente solo ofrece orientación general.';
    return 'Puedo orientarte sobre habitaciones, reservas, promociones, pagos y ubicación. Prueba con una de esas opciones; para casos particulares, comunícate directamente con recepción.';
  };

  const send = (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    addBubble(trimmed, 'user');
    addBubble(answerFor(trimmed), 'bot');
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    send(input.value);
    input.value = '';
    input.focus();
  });

  root.querySelectorAll('[data-question]').forEach((button) => {
    button.addEventListener('click', () => send(button.dataset.question));
  });
})();
