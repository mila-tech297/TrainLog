'use strict';
let state = { workouts: [], goal: null };
const $ = (selector) => document.querySelector(selector);
const format = (value, digits = 1) => Number(value).toLocaleString('nl-NL', { maximumFractionDigits: digits });
const prettyDate = (value) => new Date(value + 'T12:00:00').toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' });
let toastTimer;

function toast(text) {
  $('#toast').textContent = text;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4000);
}

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Trainlog-Token': state.token },
    body: JSON.stringify(body)
  };
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('Geen verbinding met de Python-server. Controleer of python app.py nog draait.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Er ging iets mis. Probeer opnieuw.');
  return result;
}

function weekWorkouts() {
  const start = new Date(state.today + 'T12:00:00');
  start.setDate(start.getDate() - 6);
  const date = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
  return state.workouts.filter(w => w.date >= date && w.date <= state.today);
}

function renderWorkouts(target, workouts, allowDelete) {
  const container = $(target);
  container.replaceChildren();
  if (!workouts.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'Je eerste stap begint hier. Voeg een training toe en bouw je eigen trainingsboek op.';
    container.append(empty);
    return;
  }
  for (const workout of workouts) {
    const row = document.createElement('div');
    row.className = 'workout-row';
    const icon = document.createElement('span');
    icon.className = 'run-icon'; icon.textContent = '↗'; icon.setAttribute('aria-hidden', 'true');
    const info = document.createElement('div'); info.className = 'workout-info';
    const name = document.createElement('strong'); name.textContent = 'Hardlopen';
    const details = document.createElement('small');
    const seconds = Math.round(workout.duration / workout.distance * 60);
    details.textContent = `${prettyDate(workout.date)} · ${format(workout.duration)} min · ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} /km`;
    info.append(name, details);
    if (workout.note) {
      const note = document.createElement('small'); note.className = 'note';
      note.textContent = workout.note; info.append(note);
    }
    const distance = document.createElement('span'); distance.className = 'workout-distance';
    distance.textContent = format(workout.distance, 2) + ' ';
    const unit = document.createElement('small'); unit.textContent = 'km'; distance.append(unit);
    row.append(icon, info, distance);
    if (allowDelete) {
      const remove = document.createElement('button'); remove.className = 'delete-button'; remove.textContent = '×';
      remove.setAttribute('aria-label', `Training van ${prettyDate(workout.date)} verwijderen`);
      remove.addEventListener('click', async () => {
        if (!confirm(`Training van ${prettyDate(workout.date)} verwijderen?`)) return;
        remove.disabled = true;
        try { state = await api('/api/workouts/delete', { id: workout.id }); render(); toast('Training verwijderd.'); }
        catch (error) { toast(error.message); remove.disabled = false; }
      });
      row.append(remove);
    }
    container.append(row);
  }
}

function renderChart() {
  const workouts = state.workouts.slice(0, 12).reverse();
  const container = $('#chart'); container.replaceChildren();
  if (!workouts.length) {
    const empty = document.createElement('p'); empty.className = 'chart-empty';
    empty.textContent = 'Hier groeit jouw verhaal. Sla je eerste training op om je vooruitgang te zien.';
    container.append(empty); return;
  }
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', '0 0 500 220'); svg.setAttribute('role', 'img');
  const title = document.createElementNS(svgNS, 'title'); title.id = 'chart-title';
  title.textContent = `Afstand van de laatste ${workouts.length} trainingen: ` + workouts.map(w => `${prettyDate(w.date)}: ${format(w.distance, 2)} kilometer`).join('; ') + (state.goal ? `. Doel: ${format(state.goal.distance)} kilometer.` : '');
  svg.setAttribute('aria-labelledby', 'chart-title'); svg.append(title);
  function element(tag, attributes, text) {
    const node = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    svg.append(node); return node;
  }
  const max = Math.max(...workouts.map(w => w.distance), state.goal?.distance || 0, 1) * 1.15;
  const x = i => workouts.length === 1 ? 265 : 42 + i / (workouts.length - 1) * 438;
  const y = distance => 183 - distance / max * 160;
  for (let i = 0; i <= 4; i++) {
    const distance = max * i / 4;
    element('line', { x1: 40, y1: y(distance), x2: 485, y2: y(distance), stroke: '#e9ede3', 'stroke-dasharray': '3 4' });
    element('text', { x: 30, y: y(distance) + 4, fill: '#89947d', 'font-size': 10, 'text-anchor': 'end' }, format(distance));
  }
  if (state.goal) element('line', { x1: 40, y1: y(state.goal.distance), x2: 485, y2: y(state.goal.distance), stroke: '#a5b879', 'stroke-width': 2, 'stroke-dasharray': '6 5' });
  const points = workouts.map((w, i) => `${x(i)},${y(w.distance)}`);
  element('polygon', { points: `${x(0)},183 ${points.join(' ')} ${x(workouts.length - 1)},183`, fill: '#eaf1df', opacity: '.7' });
  element('polyline', { points: points.join(' '), fill: 'none', stroke: '#658449', 'stroke-width': 3, 'stroke-linejoin': 'round' });
  workouts.forEach((w, i) => {
    const dot = element('circle', { cx: x(i), cy: y(w.distance), r: 4, fill: '#658449', stroke: 'white', 'stroke-width': 2 });
    const tooltip = document.createElementNS(svgNS, 'title'); tooltip.textContent = `${prettyDate(w.date)}: ${format(w.distance, 2)} km`; dot.append(tooltip);
    if (workouts.length <= 5 || i === 0 || i === workouts.length - 1 || i % 3 === 0)
      element('text', { x: x(i), y: 210, fill: '#89947d', 'font-size': 10, 'text-anchor': 'middle' }, prettyDate(w.date));
  });
  container.append(svg);
}

function render() {
  const week = weekWorkouts();
  $('#week-distance').textContent = format(week.reduce((total, w) => total + w.distance, 0));
  $('#week-count').textContent = week.length;
  $('#week-duration').textContent = format(week.reduce((total, w) => total + w.duration, 0));
  $('#total-count').textContent = `${state.workouts.length} trainingen`;
  $('#today-label').textContent = new Date(state.today + 'T12:00:00').toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long' });
  $('#workout-form [name=date]').max = state.today;
  $('#goal-form [name=deadline]').min = state.today;
  renderWorkouts('#recent-workouts', state.workouts.slice(0, 3), false);
  renderWorkouts('#all-workouts', state.workouts, true);
  renderChart();
  const goal = state.goal;
  const best = Math.max(0, ...state.workouts.map(w => w.distance));
  $('#goal-number').textContent = goal ? format(goal.distance) : '—';
  $('#goal-description').textContent = goal ? `In één training · doeldatum ${prettyDate(goal.deadline)} ${goal.deadline.slice(0, 4)}` : 'Geef je volgende mijlpaal een plek.';
  const percentage = goal ? Math.min(100, best / goal.distance * 100) : 0;
  $('#goal-progress').style.width = percentage + '%';
  $('#goal-progress-label').textContent = goal ? `${format(percentage, 0)}% · langste training ${format(best, 2)} km${percentage >= 100 ? ' · doel behaald!' : goal.deadline < state.today ? ' · doeldatum verstreken' : ''}` : 'Stel je eerste afstandsdoel in';
  $('#edit-goal').textContent = goal ? 'Doel aanpassen ↗' : 'Doel instellen ↗';
  if (goal) {
    $('#goal-form [name=distance]').value = goal.distance;
    $('#goal-form [name=deadline]').value = goal.deadline;
  }
  $('#ai-status').textContent = state.ai_available ? 'AI is verbonden via de Python-server.' : 'AI nog niet ingesteld. Het gewone weekoverzicht werkt wel.';
  $('#summary-output').textContent = 'Je weekoverzicht verschijnt hier zodra je het opvraagt.';
}

function navigate() {
  const view = ['overzicht', 'trainingen', 'doel'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overzicht';
  document.querySelectorAll('.view').forEach(section => { section.hidden = section.id !== view; });
  document.querySelectorAll('.nav-link').forEach(link => {
    const active = link.hash === '#' + view;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
}

$('#add-workout').addEventListener('click', () => {
  const form = $('#workout-form'); form.reset();
  form.querySelector('[name=date]').value = state.today || new Date().toLocaleDateString('en-CA');
  form.querySelector('.form-message').textContent = '';
  $('#workout-dialog').showModal();
});
$('#close-dialog').addEventListener('click', () => $('#workout-dialog').close());
$('#edit-goal').addEventListener('click', () => { location.hash = 'doel'; $('#goal-form [name=distance]').focus(); });

function connectForm(selector, path, onSuccess) {
  $(selector).addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('[type=submit]'); button.disabled = true;
    form.querySelector('.form-message').textContent = '';
    try {
      state = await api(path, Object.fromEntries(new FormData(form)));
      render(); onSuccess();
    } catch (error) { form.querySelector('.form-message').textContent = error.message; }
    finally { button.disabled = false; }
  });
}
connectForm('#workout-form', '/api/workouts', () => { $('#workout-dialog').close(); toast('Goed gedaan! Je training is opgeslagen.'); });
connectForm('#goal-form', '/api/goal', () => { location.hash = 'overzicht'; toast('Je doel is opgeslagen. Op naar je volgende stap!'); });

async function summary(ai) {
  const buttons = [$('#summary-basic'), $('#summary-ai')];
  buttons.forEach(button => { button.disabled = true; });
  $('#summary-output').textContent = ai ? 'Je AI-samenvatting wordt gemaakt…' : 'Je weekoverzicht wordt berekend…';
  try {
    const result = await api('/api/summary', { ai });
    $('#summary-output').textContent = `${result.source}\n\n${result.text}`;
  } catch (error) { $('#summary-output').textContent = error.message; }
  finally { buttons.forEach(button => { button.disabled = false; }); }
}
$('#summary-basic').addEventListener('click', () => summary(false));
$('#summary-ai').addEventListener('click', () => summary(true));
window.addEventListener('hashchange', navigate);
navigate();
api('/api/state').then(result => { state = result; render(); }).catch(error => {
  $('#connection-error').textContent = error.message; $('#connection-error').hidden = false;
});
