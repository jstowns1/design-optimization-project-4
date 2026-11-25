export function drawResponsive(canvas, draw) {
  function render() {
    const { width, height } = canvas.getBoundingClientRect();
    if (!width || !height) return;
    const ratio = Math.min(2, window.devicePixelRatio);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const context = canvas.getContext('2d');
    context.scale(ratio, ratio);
    draw(context, width, height);
  }
  new ResizeObserver(render).observe(canvas);
  render();
}

function line(context, x1, y1, x2, y2) {
  context.beginPath();
  context.moveTo(x1, y1);
  context.lineTo(x2, y2);
  context.stroke();
}

function dimension(context, start, end, y, label) {
  context.strokeStyle = '#68878b';
  context.lineWidth = 1;
  line(context, start, y, end, y);
  line(context, start - 3, y + 3, start + 3, y - 3);
  line(context, end - 3, y + 3, end + 3, y - 3);
  context.fillStyle = '#264d52';
  context.font = '600 12px Segoe UI, sans-serif';
  context.textAlign = 'center';
  context.fillText(label, (start + end) / 2, y - 7);
}

function frameDrawing(canvas, data) {
  const design = data.optimized;
  const project = ([x, y, z]) => [x - .68 * y, .22 * x + .55 * y - .92 * z];
  const projected = design.nodes.map(project);
  const horizontal = projected.map(point => point[0]);
  const vertical = projected.map(point => point[1]);
  const left = Math.min(...horizontal);
  const right = Math.max(...horizontal);
  const top = Math.min(...vertical);
  const bottom = Math.max(...vertical);
  const ordered = data.mesh.edges.map(([a, b], index) => ({
    a, b, member: data.mesh.owner[index], depth: design.nodes[a][1] + design.nodes[b][1]
  })).sort((one, two) => two.depth - one.depth);
  const { span_m: span, width_m: width } = data.dimensions;

  drawResponsive(canvas, (context, w, h) => {
    context.strokeStyle = '#d6e6e5';
    context.lineWidth = 1;
    for (let x = 16; x < w; x += 22) line(context, x, 0, x, h);
    for (let y = 16; y < h; y += 22) line(context, 0, y, w, y);

    const availableHeight = h - 50;
    const scale = Math.min((w - 38) / (right - left), (availableHeight - 14) / (bottom - top));
    const x = value => w / 2 + (value - (left + right) / 2) * scale;
    const y = value => availableHeight / 2 + 12 + (value - (top + bottom) / 2) * scale;
    const footprint = [[0, -width / 2, 0], [0, width / 2, 0], [span, width / 2, 0], [span, -width / 2, 0]];
    context.beginPath();
    footprint.map(project).forEach(([a, b], index) => {
      if (index === 0) context.moveTo(x(a), y(b));
      else context.lineTo(x(a), y(b));
    });
    context.closePath();
    context.fillStyle = '#dae9e8';
    context.fill();

    context.lineCap = 'round';
    for (const { a, b, member, depth } of ordered) {
      const [x0, y0] = projected[a];
      const [x1, y1] = projected[b];
      context.strokeStyle = depth > 0 ? '#789c9f' : '#235c62';
      context.lineWidth = Math.max(.84, 2 * design.radii_m[member] * scale);
      line(context, x(x0), y(y0), x(x1), y(y1));
    }
    context.lineCap = 'butt';
    dimension(context, w * .18, w * .82, h - 17, span.toFixed(2) + ' m span');
  });
}

function deckDrawing(canvas, data) {
  const design = data.optimized;
  const { span_m: span, width_m: width, deck_thickness_m: thickness } = data.dimensions;
  const midspan = span / 2;
  const supports = data.mesh.edges.flatMap(([a, b], index) => {
    const member = data.mesh.owner[index];
    const name = data.mesh.labels[member];
    const start = design.nodes[a];
    const end = design.nodes[b];
    if (name !== 'Stringer' && name !== 'Bottom chord') return [];
    if (start[0] >= midspan || end[0] < midspan) return [];
    return [{ y: start[1], radius: design.radii_m[member] }];
  }).sort((one, two) => one.y - two.y);

  drawResponsive(canvas, (context, w, h) => {
    const scale = (w - 56) / width;
    const x = value => w / 2 + value * scale;
    const plateY = h * .36;
    const centerY = plateY + .15 * scale + 6;
    context.fillStyle = '#264d52';
    context.font = '600 12px Segoe UI, sans-serif';
    context.textAlign = 'center';
    context.fillText((data.plate.pressure_pa / 1000).toFixed(2) + ' kPa deck pressure', w / 2, 21);
    context.strokeStyle = '#a56c36';
    context.lineWidth = 1.2;
    for (let index = 0; index < 9; index += 1) {
      const at = x(width * (index / 8 - .5));
      const tip = plateY - 6;
      line(context, at, 30, at, tip);
      line(context, at - 3, tip - 4, at, tip);
      line(context, at + 3, tip - 4, at, tip);
    }
    context.fillStyle = '#527b80';
    context.fillRect(x(-width / 2) - 5, plateY, width * scale + 10, Math.max(5, thickness * scale));

    for (const support of supports) {
      const left = x(support.y);
      const radius = support.radius * scale;
      context.fillStyle = '#dcebe9';
      context.strokeStyle = '#235c62';
      context.lineWidth = 1.15;
      context.beginPath();
      context.arc(left, centerY, radius, 0, 2 * Math.PI);
      context.moveTo(left + .9 * radius, centerY);
      context.arc(left, centerY, .9 * radius, 0, 2 * Math.PI, true);
      context.fill();
      context.stroke();
      context.strokeStyle = '#a9bfc0';
      line(context, left, centerY + radius + 3, left, h - 16);
    }
    for (let index = 1; index < supports.length; index += 1) {
      const a = supports[index - 1].y;
      const b = supports[index].y;
      dimension(context, x(a), x(b), h - 43, (b - a).toFixed(2) + ' m');
    }
    dimension(context, x(-width / 2), x(width / 2), h - 16, width.toFixed(2) + ' m clear width');
  });
}

export function renderEngineeringFigures(results) {
  frameDrawing(document.getElementById('frame-diagram'), results);
  deckDrawing(document.getElementById('deck-diagram'), results);
}
