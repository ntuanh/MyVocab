// File: static/js/charts.js
// Draws an IELTS Task 1 chart (line, bar, pie or table) as SVG from the data in
// data/writing/task1.json. Series take the colour slots --series-1.. in a fixed
// order (style.css steps them for the night look); a legend names them, every
// value is in the hover readout, and "Show the data as a table" holds the same
// numbers without the picture.

(function () {
    const SVG = 'http://www.w3.org/2000/svg';
    const MAX_W = 640;  // drawn at the width available, up to this, so text keeps its size

    function svg(tag, attrs = {}, text) {
        const node = document.createElementNS(SVG, tag);
        Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    const colour = i => `var(--series-${(i % 6) + 1})`;

    // A clean top for the axis: 1, 2, 2.5 or 5 times a power of ten, with 4-5 steps.
    function axis(max) {
        const raw = max / 5;
        const power = 10 ** Math.floor(Math.log10(raw || 1));
        const step = [1, 2, 2.5, 5, 10].map(s => s * power).find(s => s >= raw);
        return { step, top: Math.ceil(max / step) * step };
    }

    // --- hover / focus readout (enhances only; the table has every value) ---
    let tip = null;
    function showTip(target, value, name) {
        if (!tip) {
            tip = el('div', 'viz-tooltip');
            tip.setAttribute('aria-hidden', 'true');
            document.body.append(tip);
        }
        tip.replaceChildren(el('div', 'tip-value', value), el('div', 'tip-name', name));
        tip.hidden = false;
        const m = target.getBoundingClientRect();
        const t = tip.getBoundingClientRect();
        tip.style.left = `${Math.min(Math.max(8, m.left + m.width / 2 - t.width / 2), innerWidth - t.width - 8)}px`;
        tip.style.top = `${m.top - t.height - 8 < 8 ? m.bottom + 8 : m.top - t.height - 8}px`;
    }
    function hideTip() { if (tip) tip.hidden = true; }
    function hover(node, value, name) {
        node.setAttribute('tabindex', '0');
        node.setAttribute('aria-label', `${name}: ${value}`);
        node.addEventListener('pointerenter', () => showTip(node, value, name));
        node.addEventListener('focus', () => showTip(node, value, name));
        node.addEventListener('pointerleave', hideTip);
        node.addEventListener('blur', hideTip);
    }

    function legend(names) {
        const ul = el('ul', 'chart-legend');
        names.forEach((name, i) => {
            const li = el('li');
            const key = el('span', 'chart-key');
            key.style.background = colour(i);
            li.append(key, name);
            ul.append(li);
        });
        return ul;
    }

    function fmt(v, unit) {
        return unit === '%' ? `${v}%` : `${v.toLocaleString('en-GB')}${unit ? ` ${unit}` : ''}`;
    }

    // --- line and bar: one value axis, categories along the bottom ---
    function axes(root, chart, plot, top) {
        const { step } = axis(top);
        for (let v = 0; v <= top + 1e-9; v += step) {
            const y = plot.y + plot.h - (v / top) * plot.h;
            root.append(svg('line', { x1: plot.x, x2: plot.x + plot.w, y1: y, y2: y, class: 'chart-grid' }));
            root.append(svg('text', { x: plot.x - 8, y: y + 4, class: 'chart-tick', 'text-anchor': 'end' },
                Number.isInteger(v) ? v.toLocaleString('en-GB') : v));
        }
        root.append(svg('text', { x: plot.x - 44, y: plot.y - 18, class: 'chart-unit' }, chart.unit));
    }

    function lineChart(chart, W) {
        const narrow = W < 480;  // too narrow for names at the line ends; the legend has them
        const plot = { x: 60, y: 40, w: W - 60 - (narrow ? 16 : 130), h: narrow ? 200 : 250 };
        const height = plot.y + plot.h + 40;
        const root = svg('svg', { viewBox: `0 0 ${W} ${height}`, class: 'chart-svg', role: 'img',
            'aria-label': `${chart.title}. Line graph; the table below has every value.` });
        const top = axis(Math.max(...chart.series.flatMap(s => s.values))).top;
        axes(root, chart, plot, top);
        const xAt = i => plot.x + (chart.x.length === 1 ? plot.w / 2 : (i / (chart.x.length - 1)) * plot.w);
        const yAt = v => plot.y + plot.h - (v / top) * plot.h;
        chart.x.forEach((label, i) => root.append(svg('text', { x: xAt(i), y: plot.y + plot.h + 22, class: 'chart-tick', 'text-anchor': 'middle' }, label)));
        const ends = [];
        chart.series.forEach((s, si) => {
            const points = s.values.map((v, i) => `${xAt(i)},${yAt(v)}`).join(' ');
            root.append(svg('polyline', { points, class: 'chart-line', style: `stroke: ${colour(si)}` }));
            s.values.forEach((v, i) => {
                root.append(svg('circle', { cx: xAt(i), cy: yAt(v), r: 4, class: 'chart-dot', style: `fill: ${colour(si)}` }));
                const hit = svg('circle', { cx: xAt(i), cy: yAt(v), r: 12, class: 'chart-hit' });
                hover(hit, fmt(v, chart.unit), `${s.name}, ${chart.x[i]}`);
                root.append(hit);
            });
            ends.push({ name: s.name, y: yAt(s.values[s.values.length - 1]) });
        });
        // Direct labels at the line ends, unless two would collide (the legend still names them).
        ends.sort((a, b) => a.y - b.y);
        const apart = !narrow && ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= 15);
        if (apart) ends.forEach(e => root.append(svg('text', { x: plot.x + plot.w + 10, y: e.y + 4, class: 'chart-end' }, e.name)));
        return root;
    }

    // A bar with a 4px rounded top and a square base.
    function barPath(x, y, w, h) {
        const r = Math.min(4, w / 2, h);
        return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
    }

    function barChart(chart, W) {
        const plot = { x: 60, y: 40, w: W - 80, h: W < 480 ? 200 : 250 };
        const height = plot.y + plot.h + 40;
        const root = svg('svg', { viewBox: `0 0 ${W} ${height}`, class: 'chart-svg', role: 'img',
            'aria-label': `${chart.title}. Bar chart; the table below has every value.` });
        const top = axis(Math.max(...chart.series.flatMap(s => s.values))).top;
        axes(root, chart, plot, top);
        const band = plot.w / chart.x.length;
        const n = chart.series.length;
        const barW = Math.min(24, (band * 0.7 - (n - 1) * 2) / n);
        chart.x.forEach((label, ci) => {
            const groupW = n * barW + (n - 1) * 2;
            const x0 = plot.x + ci * band + (band - groupW) / 2;
            root.append(svg('text', { x: plot.x + ci * band + band / 2, y: plot.y + plot.h + 22, class: 'chart-tick', 'text-anchor': 'middle' }, label));
            chart.series.forEach((s, si) => {
                const v = s.values[ci];
                const h = Math.max(1, (v / top) * plot.h);
                const bar = svg('path', { d: barPath(x0 + si * (barW + 2), plot.y + plot.h - h, barW, h), class: 'chart-bar', style: `fill: ${colour(si)}` });
                hover(bar, fmt(v, chart.unit), `${s.name}, ${label}`);
                root.append(bar);
            });
        });
        root.append(svg('line', { x1: plot.x, x2: plot.x + plot.w, y1: plot.y + plot.h, y2: plot.y + plot.h, class: 'chart-base' }));
        return root;
    }

    function pieChart(chart, W) {
        const count = chart.pies.length;
        const stacked = count > 1 && W < 480;  // too narrow for pies side by side
        const across = stacked ? 1 : count;
        const r = Math.min(across === 1 ? 105 : 95, W / (2 * across) - 40);
        const block = 2 * r + 80;
        const height = stacked ? count * block : block + 10;
        const root = svg('svg', { viewBox: `0 0 ${W} ${height}`, class: 'chart-svg', role: 'img',
            'aria-label': `${chart.title}. Pie chart${count > 1 ? 's' : ''}; the table below has every value.` });
        const names = [...new Set(chart.pies.flatMap(p => p.slices.map(s => s.name)))];
        chart.pies.forEach((pie, pi) => {
            const cx = across === 1 ? W / 2 : W * (pi + 0.5) / count;
            const top = stacked ? pi * block : 0;
            const cy = top + r + 40;
            let start = -Math.PI / 2;
            pie.slices.forEach(slice => {
                const angle = (slice.value / 100) * Math.PI * 2;
                const end = start + angle;
                const large = angle > Math.PI ? 1 : 0;
                const p = (a, rr) => `${cx + Math.cos(a) * rr},${cy + Math.sin(a) * rr}`;
                const path = svg('path', { d: `M${cx},${cy}L${p(start, r)}A${r},${r} 0 ${large} 1 ${p(end, r)}Z`,
                    class: 'chart-slice', style: `fill: ${colour(names.indexOf(slice.name))}` });
                hover(path, `${slice.value}%`, `${slice.name}, ${pie.label}`);
                root.append(path);
                const mid = start + angle / 2;
                const lx = cx + Math.cos(mid) * (r + 16);
                const ly = cy + Math.sin(mid) * (r + 16);
                root.append(svg('text', { x: lx, y: ly + 4, class: 'chart-pie-label',
                    'text-anchor': Math.abs(Math.cos(mid)) < 0.2 ? 'middle' : Math.cos(mid) > 0 ? 'start' : 'end' }, `${slice.value}%`));
                start = end;
            });
            root.append(svg('text', { x: cx, y: top + 20, class: 'chart-pie-title', 'text-anchor': 'middle' }, pie.label));
        });
        return { root, names };
    }

    function table(chart) {
        const t = el('table', 'chart-table');
        const head = el('tr');
        chart.columns.forEach((c, i) => head.append(el('th', i === 0 ? '' : 'num', c)));
        const thead = el('thead');
        thead.append(head);
        const body = el('tbody');
        chart.rows.forEach(row => {
            const tr = el('tr');
            row.forEach((cell, i) => tr.append(el(i === 0 ? 'th' : 'td', i === 0 ? '' : 'num', typeof cell === 'number' ? cell.toLocaleString('en-GB') : cell)));
            body.append(tr);
        });
        t.append(thead, body);
        return t;
    }

    // The same numbers as a table, for the chart forms that are pictures.
    function dataTable(chart) {
        if (chart.kind === 'pie') {
            const names = [...new Set(chart.pies.flatMap(p => p.slices.map(s => s.name)))];
            return table({ columns: ['', ...chart.pies.map(p => `${p.label} (%)`)],
                rows: names.map(n => [n, ...chart.pies.map(p => (p.slices.find(s => s.name === n) || {}).value ?? '')]) });
        }
        return table({ columns: ['', ...chart.series.map(s => s.name)],
            rows: chart.x.map((x, i) => [x, ...chart.series.map(s => s.values[i])]) });
    }

    function render(figure, chart) {
        const W = Math.round(Math.max(300, Math.min(MAX_W, figure.clientWidth - 34)));
        figure.dataset.drawnAt = W;
        const caption = el('figcaption', 'chart-title', chart.title);
        if (chart.unit && chart.kind === 'table') caption.append(el('span', 'chart-caption-unit', ` (${chart.unit})`));
        const parts = [caption];
        if (chart.kind === 'table') {
            parts.push(table(chart));
        } else {
            let drawing;
            let names = chart.series ? chart.series.map(s => s.name) : [];
            if (chart.kind === 'line') drawing = lineChart(chart, W);
            if (chart.kind === 'bar') drawing = barChart(chart, W);
            if (chart.kind === 'pie') ({ root: drawing, names } = pieChart(chart, W));
            if (names.length > 1) parts.push(legend(names));
            parts.push(drawing);
            const details = el('details', 'chart-data');
            details.append(el('summary', '', 'Show the data as a table'), dataTable(chart));
            parts.push(details);
        }
        figure.replaceChildren(...parts);
        // Redrawn when the space it has changes a lot (a phone turned, a window resized).
        figure.chartData = chart;
        if (!figure.chartWatch && 'ResizeObserver' in window) {
            figure.chartWatch = new ResizeObserver(() => {
                const width = Math.round(Math.max(300, Math.min(MAX_W, figure.clientWidth - 34)));
                if (figure.chartData && figure.clientWidth && Math.abs(width - Number(figure.dataset.drawnAt)) > 40) {
                    render(figure, figure.chartData);
                }
            });
            figure.chartWatch.observe(figure);
        }
    }

    window.MyVocabCharts = { render };
})();
