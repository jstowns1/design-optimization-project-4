const labels = [
  ['mass_kg', 'Mass', 'kg', 0, null],
  ['stress_mpa', 'R1 · Peak tube stress', 'MPa', 2, 'max'],
  ['goodman', 'R2 · Goodman factor', '', 3, 'min'],
  ['deflection_mm', 'R3 · Deck deflection', 'mm', 2, 'max'],
  ['frequency_hz', 'R4 · First frequency', 'Hz', 3, 'min'],
  ['buckling_factor', 'R5 · Buckling factor', '', 3, 'min'],
  ['slenderness', 'R6 · Max slenderness', '', 1, 'max']
];

const id = name => document.getElementById(name);
const number = (value, digits = 2) => value.toLocaleString('en-US', {
  minimumFractionDigits: digits, maximumFractionDigits: digits
});
const withUnit = (value, digits, unit) => number(value, digits) + (unit ? ' ' + unit : '');
const scientific = value => value === 0 ? '0' : value.toExponential(2);
const significant = value => Number(value.toPrecision(9)).toLocaleString('en-US', { maximumFractionDigits: 10 });

function table(host, headers, rows) {
  const element = document.createElement('table');
  const head = element.createTHead().insertRow();
  headers.forEach(label => {
    const column = document.createElement('th');
    column.scope = 'col';
    column.textContent = label;
    head.append(column);
  });
  const body = element.createTBody();
  rows.forEach(values => {
    const row = body.insertRow();
    values.forEach(value => { row.insertCell().textContent = value; });
  });
  host.replaceChildren(element);
}

function metricGrid(name, values, limits) {
  const list = document.createElement('dl');
  list.className = 'metrics';
  labels.forEach(([key, label, unit, decimals, sense]) => {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    const value = document.createElement('dd');
    term.textContent = label;
    value.textContent = withUnit(values[key], decimals, unit);
    if (sense) {
      const margin = sense === 'max' ? limits[key] - values[key] : values[key] - limits[key];
      const passed = margin >= -1e-8 * limits[key];
      value.className = passed ? 'pass' : 'fail';
      value.append(passed ? ' · Pass' : ' · Fail');
    }
    item.append(term, value);
    list.append(item);
  });
  id(name + '-metrics').replaceChildren(list);
}

function plot(canvas, curves, axes) {
  const colors = ['#28735e', '#374b89', '#a35427', '#9a326a', '#456931', '#745190', '#526760'];
  const points = curves.flatMap(curve => curve.points);
  const xs = points.map(([x]) => axes.log ? Math.log10(x) : x);
  const ys = points.map(([, y]) => axes.log ? Math.log10(Math.max(1e-16, y)) : y);
  const minX = axes.log ? Math.floor(Math.min(...xs)) : Math.min(...xs);
  const maxX = axes.log ? Math.ceil(Math.max(...xs)) : Math.max(...xs);
  const minY = axes.log ? Math.floor(Math.min(...ys)) : Math.floor(Math.min(...ys) / 500) * 500;
  const maxY = axes.log ? Math.ceil(Math.max(...ys)) : Math.ceil(Math.max(...ys) / 500) * 500;

  function draw() {
    const ctx = canvas.getContext('2d');
    const { width, height } = canvas.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.scale(ratio, ratio);
    const box = { left: 61, right: width - 17, top: 17, bottom: height - 77 };
    const mapX = (x) => box.left + (box.right - box.left) * (x - minX) / (maxX - minX);
    const mapY = (y) => box.bottom - (box.bottom - box.top) * (y - minY) / (maxY - minY);
    ctx.font = '11px Segoe UI, sans-serif';
    ctx.fillStyle = '#455d53';
    ctx.strokeStyle = '#dde8e2';
    const tickCount = 6;
    for (let tick = 0; tick <= tickCount; tick += 1) {
      const y = minY + (maxY - minY) * tick / tickCount;
      const pixel = mapY(y);
      ctx.beginPath();
      ctx.moveTo(box.left, pixel);
      ctx.lineTo(box.right, pixel);
      ctx.stroke();
      ctx.textAlign = 'right';
      ctx.fillText(axes.log ? '1e' + y.toFixed(1) : number(y, 0), box.left - 7, pixel + 4);
      const x = minX + (maxX - minX) * tick / tickCount;
      ctx.textAlign = 'center';
      ctx.fillText(axes.log ? '1e' + x.toFixed(1) : number(x, 0), mapX(x), box.bottom + 15);
    }
    ctx.fillText(axes.x, (box.left + box.right) / 2, box.bottom + 31);
    ctx.save();
    ctx.translate(13, (box.top + box.bottom) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(axes.y, 0, 0);
    ctx.restore();
    curves.forEach((curve, index) => {
      const color = colors[index];
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = curve.reference ? 1 : 1.65;
      ctx.setLineDash(curve.reference ? [4, 4] : []);
      ctx.beginPath();
      curve.points.forEach(([x, y], point) => {
        const xx = mapX(axes.log ? Math.log10(x) : x);
        const yy = mapY(axes.log ? Math.log10(Math.max(1e-16, y)) : y);
        if (point === 0) ctx.moveTo(xx, yy);
        else ctx.lineTo(xx, yy);
      });
      ctx.stroke();
      ctx.setLineDash([]);
      const columns = width < 520 ? 3 : 4;
      const legendX = 15 + (width - 22) / columns * (index % columns);
      const legendY = box.bottom + 46 + 13 * Math.floor(index / columns);
      ctx.textAlign = 'left';
      ctx.fillRect(legendX, legendY - 6, 9, 2);
      ctx.fillText(curve.label, legendX + 13, legendY - 2);
    });
  }
  new ResizeObserver(draw).observe(canvas);
}

function populate(results) {
  const { initial, optimized, refined, gradients, verification, runs, plate, limits } = results;
  const baseline = initial.metrics;
  const final = optimized.metrics;
  const noR5 = results.without_buckling.metrics;
  const massReduction = 100 * (1 - final.mass_kg / baseline.mass_kg);
  const summary = {
    'initial.mass_kg': withUnit(baseline.mass_kg, 0, 'kg'),
    'optimized.mass_kg': withUnit(final.mass_kg, 0, 'kg'),
    mass_reduction: number(massReduction, 1) + '%',
    variables: results.mesh.variables, 'mesh.members': results.mesh.members,
    'mesh.elements': results.mesh.elements, 'mesh.nodes': results.mesh.nodes,
    'plate.limit_mpa': withUnit(plate.limit_mpa, 2, 'MPa'),
    'plate.pressure_pa': withUnit(plate.pressure_pa / 1000, 3, 'kPa'),
    'plate.stress_mpa': withUnit(plate.stress_mpa, 2, 'MPa')
  };
  document.querySelectorAll('[data-value]').forEach(node => { node.textContent = summary[node.dataset.value]; });
  metricGrid('initial', baseline, limits);
  metricGrid('optimized', final, limits);

  table(id('verification-table'), ['Test', 'Quantity', 'FE result', 'Reference', 'Relative error'],
    verification.map(row => [row.test, row.quantity, significant(row.computed) + ' ' + row.units,
      significant(row.reference) + ' ' + row.units, scientific(row.error)]));
  const meshSizes = [1, .5, .25, .125];
  plot(id('mesh-plot'), [['V3 · Frequency', 'V3'], ['V4 · Buckling', 'V4']].map(([label, test]) => ({
    label, points: verification.filter(row => row.test === test).map((row, index) => [meshSizes[index], row.error])
  })).concat({ label: 'Slope 4', points: meshSizes.map(h => [h, .14 * h**4]), reference: true }),
  { x: 'Relative element length', y: 'Relative error', log: true });
  table(id('gradient-table'), ['Direction', 'Response', 'Adjoint', 'Centered difference', 'Scaled error', 'Step'],
    gradients.checks.map(row => [row.direction, row.response, scientific(row.adjoint), scientific(row.central),
      scientific(row.error), scientific(row.step)]));
  const speed = gradients.central_seconds / gradients.adjoint_seconds;
  id('timing-summary').textContent = 'V6 passed in all six directions. The full ' + gradients.finite_solves +
    '-solve centered-difference Jacobian differed by at most ' + scientific(gradients.max_absolute_jacobian_error) +
    ' in normalized output units. One adjoint evaluation took ' + number(gradients.adjoint_seconds, 3) +
    ' s versus ' + number(gradients.central_seconds, 2) + ' s for centered differences on the same machine (' +
    number(speed, 0) + '×). The table shows the best step for each check.';
  const benchmark = gradients.steps.filter(step => step >= 1e-4).map(step => [step, .09 * step**2]);
  plot(id('taylor-plot'), [...gradients.curves.map(curve => ({
    label: curve.label, points: gradients.steps.map((step, index) => [step, curve.errors[index]])
  })), { label: 'Slope 2', points: benchmark, reference: true }],
  { x: 'Perturbation step', y: 'Absolute error', log: true });

  id('optimization-summary').textContent = 'The two R5-constrained runs converged in ' +
    runs.baseline.iterations + ' and ' + runs.alternate.iterations + ' major iterations from ' +
    results.start_masses_kg.map(mass => withUnit(mass, 0, 'kg')).join(' and ') +
    '. Their final masses were ' + results.final_masses_kg.map(mass => withUnit(mass, 2, 'kg')).join(' and ') +
    '. At the selected design the portal height is ' + withUnit(optimized.portal_height_m, 3, 'm') +
    ', the camber is ' + withUnit(optimized.camber_m, 2, 'm') + ', and tube radii range from ' +
    number(Math.min(...optimized.radii_m) * 1000, 1) + ' to ' + withUnit(Math.max(...optimized.radii_m) * 1000, 1, 'mm') + '.';
  plot(id('history-plot'), [['Start 1', runs.baseline], ['Start 2', runs.alternate],
    ['Without R5', runs.without_buckling]].map(([label, run]) => ({
    label, points: run.history.map(item => [item.iteration, item.mass_kg])
  })), { x: 'Major iteration', y: 'Mass (kg)', log: false });
  const certificate = runs.selected.kkt;
  id('kkt-summary').textContent = 'The scaled KKT stationarity residual is ' + scientific(certificate.stationarity_inf) +
    ', the largest primal violation is ' + scientific(certificate.primal_violation) +
    ', and the complementarity residual is ' + scientific(certificate.complementarity_inf) +
    '. The conservative fatigue and frequency constraints are active, along with selected member slenderness limits and the camber bound.';
  const multipliers = certificate.multipliers.filter(row => row.kg > 1e-5);
  const groups = multipliers.filter(row => !row.name.startsWith('Member')).map(row => [
    row.name, withUnit(row.kg, 2, row.name === 'Camber upper bound' ? 'kg per m' : 'kg per unit')
  ]);
  for (const [suffix, label] of [['slenderness', 'R6 · Uniform relaxation'], ['radius lower bound', 'Minimum radius · Uniform relaxation']]) {
    const sum = multipliers.filter(row => row.name.endsWith(suffix)).reduce((total, row) => total + row.kg, 0);
    if (sum > 0) groups.push([label, withUnit(sum, 2, 'kg per normalized unit')]);
  }
  table(id('kkt-table'), ['Active limit', 'Local mass sensitivity'], groups);

  id('buckling-summary').textContent = 'R5 is inactive at the optimized design. Removing it changed mass by ' +
    withUnit(Math.abs(noR5.mass_kg - final.mass_kg), 3, 'kg') + ' and gave a buckling factor of ' +
    number(noR5.buckling_factor, 3) + ', above the required 3.0. The selected design retains a factor of ' +
    number(refined.buckling_factor, 3) + ' after mesh refinement.';
  table(id('results-table'), ['Metric', 'Limit', 'Initial', 'Optimized', 'Without R5', 'Refined'],
    labels.map(([key, label, unit, digits, sense]) => [label,
      sense ? (sense === 'max' ? '≤ ' : '≥ ') + withUnit(limits[key], digits, unit) : 'Minimize',
      ...[baseline, final, noR5, refined].map(values => withUnit(values[key], digits, unit))]));
}

async function main() {
  const status = id('viewer-status');
  try {
    const response = await fetch(new URL('./results.json', import.meta.url));
    if (!response.ok) throw new Error('Unable to load results (' + response.status + ').');
    const results = await response.json();
    populate(results);
    try {
      const { startViewer } = await import('./viewer.js');
      startViewer(results);
    } catch (err) {
      status.textContent = 'The 3D viewer requires WebGL and access to the Three.js module. The metrics and report remain available.';
      document.querySelectorAll('.viewer-controls :is(button,input)').forEach(control => { control.disabled = true; });
      console.error(err);
    }
  } catch (err) {
    status.textContent = 'Could not load the report results. Serve the page over HTTP and regenerate assets/results.json if needed.';
    console.error(err);
  }
}

main();
