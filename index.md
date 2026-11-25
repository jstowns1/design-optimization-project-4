---
layout: default
title: Sizing a 15 m Steel Footbridge
---

<header class="report-cover">
  <div class="cover-text">
    <p class="course-label">MAE 494/598 · Project 4</p>
    <h1>Sizing a 15 m<br> steel footbridge</h1>
    <p class="abstract">We optimize the tube sizes and top-chord profile of a Pratt through-truss under pedestrian load and self-weight. The design must satisfy strength, fatigue, deflection, vibration, stability, and slenderness limits.</p>
  </div>
  <figure class="cover-figure">
    <canvas id="frame-diagram" role="img" aria-label="Axonometric drawing of the optimized six-bay Pratt through-truss, generated from the finite-element model"></canvas>
    <figcaption>Optimized frame in the undeformed configuration</figcaption>
  </figure>
</header>

<div class="summary" aria-label="Study highlights">
  <div><span>Initial mass</span><strong data-value="initial.mass_kg">…</strong></div>
  <div><span>Optimized mass</span><strong data-value="optimized.mass_kg">…</strong></div>
  <div><span>Mass reduction</span><strong data-value="mass_reduction">…</strong></div>
</div>

<section class="comparison" id="comparison" aria-labelledby="comparison-heading">
  <div class="comparison-heading">
    <h2 id="comparison-heading">Initial and optimized designs</h2>
    <p>Drag to orbit both views. Scroll or pinch to zoom. Select a tube to inspect it.</p>
  </div>
  <div class="viewer-controls">
    <label for="exaggeration">Static deflection <output id="exaggeration-value" for="exaggeration">20×</output></label>
    <input id="exaggeration" type="range" min="0" max="100" step="1" value="20">
    <button id="animate-mode" type="button" aria-pressed="false">Play buckling mode</button>
    <button id="reset-camera" type="button">Reset view</button>
  </div>
  <div class="paired">
    <article><h3>Initial design</h3><div class="stage" id="initial-view" aria-label="Initial bridge model"></div><p class="inspection" id="initial-inspect" aria-live="polite">Select an element to see its radius and stress.</p><div id="initial-metrics"></div></article>
    <article><h3>Optimized design</h3><div class="stage" id="optimized-view" aria-label="Optimized bridge model"></div><p class="inspection" id="optimized-inspect" aria-live="polite">Select an element to see its radius and stress.</p><div id="optimized-metrics"></div></article>
  </div>
  <div class="legend"><strong>Tube stress as a share of the fatigue limit</strong><span class="legend-scale"><span>0%</span><span class="ramp"></span><span>150%+</span></span><span><i></i> Over limit</span></div>
  <p class="viewer-help">Tube radii are drawn at true scale. The translucent plate marks the undeformed deck. The mode animation uses a display amplitude of 0.35 m.</p>
  <p class="viewer-help" id="viewer-status" role="status" aria-live="polite"></p>
</section>

## Formulation

The fixed geometry spans 15 m in six 2.5 m bays. The bottom chords and three interior stringers support an 8 mm steel plate with 0.75 m transverse spacing. Floor beams tie the stringers into two side trusses. Rigid overhead cross members and diagonals carry lateral forces between the trusses. The design trades material use against pedestrian serviceability and the fatigue life of the members. Coordinates use $x$ along the span and $z$ upward.

The design has <span data-value="variables">…</span> variables. Every physical tube has its own outer radius $r_j\in[10,150]$ mm and a wall thickness of $0.1r_j$. Two shape variables control the top chord elevation $z(x)=h+4c(x/L)(1-x/L)$, where $h\in[2.45,3.40]$ m and $c\in[0,0.65]$ m. The bounds keep the overhead framing above the deck and limit its rise in this design study. The deck elevation, bearing lines, and spanwise joint locations stay fixed.

For steel, $E=200$ GPa, $\nu=0.3$, $G=E/[2(1+\nu)]$, and $\rho=7850$ kg/m³. With $r_i=0.9r_j$, the sections have $A=\pi(r_j^2-r_i^2)$, $I=\pi(r_j^4-r_i^4)/4$, $J=2I$, and radius of gyration $r_g=\sqrt{I/A}$. We minimize $m=\rho\sum_j A_j L_j+\rho bLt$, with $b=3$ m and $t=0.008$ m for the deck. The limits come from the steel footbridge specification, pp. 10–13 and 15. [Project 4 handout](https://designinformaticslab.github.io/DesignOptimization2025/project4.html)

| Requirement | Physical constraint | Limit |
| --- | --- | ---: |
| R1 Static strength | Maximum end-section von Mises stress $\sigma_{\mathrm{vM}}$ | 160 MPa |
| R2 Goodman fatigue | $n_f=\{(\sigma_{\mathrm{vM}}/2)[1/S_e+1/S_{ut}]\}^{-1}$ at the worst section | $n_f\ge 2$ |
| R3 Deck deflection | $\max_{e,\xi}\lvert w_e(\xi)\rvert$ over the deck beam curves, $\xi\in[0,1]$ | $L/400=37.5$ mm |
| R4 Vibration | Lowest natural frequency $f_1=\sqrt{\lambda_1}/(2\pi)$ | $f_1\ge 3$ Hz |
| R5 Stability, route S1 | Lowest positive linear buckling factor $\alpha_1$ | $\alpha_1\ge 3$ |
| R6 Slenderness | Member slenderness $L_j/r_{g,j}$ using the full length of each physical member | $L_j/r_{g,j}\le 200$ |

At each element end, $\sigma_n=\lvert N\rvert/A+r_j\sqrt{M_y^2+M_z^2}/I$, $\tau=Tr_j/J$, and $\sigma_{\mathrm{vM}}=\sqrt{\sigma_n^2+3\tau^2}$. The handout uses zero-to-full-load fatigue cycles with $S_e=0.7(86.2\text{ MPa})$ and $S_{ut}=460$ MPa. This gives the equivalent fatigue limit <span data-value="plate.limit_mpa">…</span>, which governs before R1. Limit comparisons in the results table use the physical extrema.

## Analysis model

Each node has three translations and three rotations. The degrees of freedom are assembled into the sparse equilibrium system $Ku=F$. The member equations are $EAu''+p_x=0$ for axial motion, $EIw''''=q$ in each bending plane, and $GJ\theta''+m_x=0$ in torsion. Linear interpolation is used for axial and twist DOFs and cubic Hermite interpolation for transverse displacements. Element transformations rotate all six nodal DOFs between the member and global coordinates. There are <span data-value="mesh.members">…</span> physical members, <span data-value="mesh.elements">…</span> beam elements, and <span data-value="mesh.nodes">…</span> nodes. Each member has two elements.

The left deck bearing line fixes $u_x,u_y,u_z$ and the right bearing line fixes $u_y,u_z$. Rotations are free on both lines. Member self-weight acts as a consistent line load. Under deck option D2, the full pedestrian pressure of 5.0 kPa and deck self-weight act on the stringers and lower chords using their tributary widths. The plate mass is distributed to the nodes of those beam segments for vibration. The vibration mass includes the frame and the deck. The frame uses consistent translational beam mass and polar rotary inertia for torsion.

<figure class="engineering-figure">
  <canvas id="deck-diagram" role="img" aria-label="Dimensioned section of the bridge deck showing four equal transverse bays between five tube supports"></canvas>
  <figcaption>Transverse deck section in the D2 model. An 8 mm plate spans across the two bottom chords and three interior stringers. The drawing separates the plate from the tube sections and exaggerates its thickness for legibility.</figcaption>
</figure>

For the independent plate strip check, a 1 m wide simply supported strip spans 0.75 m. Its uniform service pressure is <span data-value="plate.pressure_pa">…</span>. With moment $q s^2/8$ and section modulus $t^2/6$, the plate stress is $0.75qs^2/t^2=$ <span data-value="plate.stress_mpa">…</span>. This is below the fatigue limit. The deck plate stiffness is omitted from the frame.

## Verification

The ladder covers the team's original V1 check, 3D bending and torsion, a rotated uniform-load beam, mesh refinement for vibration and buckling, rigid-body modes, and global equilibrium. V6 checks the derivatives used by the optimizer. The exact beam expressions come from the assignment handout. [Original V1 calculation](https://github.com/jstowns1/design-optimization-project-4/blob/main/benchmarks.md)

<details class="report-details" open>
  <summary>V1–V5 benchmark results</summary>
  <div class="table-scroll" id="verification-table"></div>
</details>

<figure><canvas id="mesh-plot" aria-label="Log-log plot of vibration and column buckling error versus relative element length"></canvas><figcaption>V3 and V4 relative errors versus element length divided by span. The reference line shows fourth-order convergence.</figcaption></figure>

The one-element Euler result is sensitive to interpolation, so the buckling benchmark is verified by refinement. The production model uses two elements per member and the selected design is checked again with four elements per member in the results table.

## Sensitivities

Write the static residual as $R(d,u)=K(d)u-F(d)$. For a scalar response $q$, the adjoint solves $K^T\psi=-q_u^T$, so $dq/dd=q_d+\psi^T(K_d u-F_d)$. The self-weight derivative enters $F_d$. Stress derivatives include both the section-scaled end actions and the explicit $A,I,J$ terms. Mass and slenderness depend explicitly on member lengths and section properties.

For deck deflection, the Hermite curve is represented by four cubic Bézier controls $(w_0,\ w_0+\ell w'_0/3,\ w_1-\ell w'_1/3,\ w_1)$. The curve lies within the range of its controls. Their linear map from the deck DOFs gives the adjoint right-hand side by transposition. For reporting, we recover the physical maximum on the finite-element curve by evaluating both endpoints and all interior stationary points.

The eigenvector for vibration is mass-normalized, giving $\lambda_d=\phi^T(K_d-\lambda M_d)\phi$. For buckling we solve $-K_G\varphi=\mu K\varphi$ with $\varphi^T K\varphi=1$ and $\alpha=1/\mu$. The eigenvalue derivative is $\mu_d=\varphi^T(-dK_G/dd-\mu K_d)\varphi$. The geometric matrix is constructed from each element's mean equilibrium axial force. Its displacement derivative contributes to the buckling adjoint right-hand side, and its local geometry and load derivatives contribute to the explicit term.

The normalized constraints are conservative Kreisselmeier–Steinhauser upper bounds on the end stress ratios, both signs of the deck Bézier control ratios, $3/f_i$ for the lowest six frequencies, and $3\mu_i$ for the largest six inverse buckling factors. Subtract one from each aggregate to obtain $g\le 0$. The radius derivatives are analytic. For the two shape variables, the local element maps are differentiated by complex step with the solved displacement held fixed. One sparse factorization is reused across the static and adjoint solves.

<p id="timing-summary"></p>
<figure><canvas id="taylor-plot" aria-label="Log-log plot of centered finite difference derivative error versus step size"></canvas><figcaption>Largest absolute derivative error over all normalized outputs in each direction. A slope of two is the central-difference reference.</figcaption></figure>
<details class="report-details">
  <summary>V6 directional derivative results</summary>
  <div class="table-scroll" id="gradient-table"></div>
</details>

## Optimization

SLSQP minimizes mass divided by 10,000 kg. The tube radii are scaled by 50 mm, and the two shape variables are in metres. R6 is imposed individually for each member. The first start uses 75 mm radii with shape $(h,c)=(2.65,0.25)$ m. The alternate start uses 95 mm radii and $(3.15,0.10)$ m. We ran both starts with R5 included and repeated the first with R5 removed. Each run uses the adjoint derivatives and a deterministic eigensolver start vector.

<p id="optimization-summary"></p>
<figure><canvas id="history-plot" aria-label="Plot of SLSQP mass against iteration for two starts and the no R5 run"></canvas><figcaption>SLSQP mass by major iteration. The iterates can temporarily violate constraints.</figcaption></figure>
<p id="kkt-summary"></p>
<div class="table-scroll" id="kkt-table"></div>

The KKT multipliers are recovered by nonnegative least squares on the gradients of active inequalities and bounds. For a normalized response constraint, multiplying its multiplier by 10,000 kg gives the predicted local mass decrease per unit increase in the allowable normalized response. The table lists the nonzero response multipliers and combines the slenderness multipliers for a uniform relaxation across members.

## Nonlinear component and results

The N1 stability analysis finds the first buckling factor by linearizing about the preloaded state. Compression contributes negative geometric stiffness to the lateral modes. The viewer animates the first buckling eigenvector around the displayed static state. Mode amplitude and sign are arbitrary in a linearized eigenproblem.

<p id="buckling-summary"></p>
<div class="table-scroll" id="results-table"></div>

The higher-resolution column reanalyzes the selected design at four elements per physical member. The study assumes ideal rigid joints, a one-way deck strip, nominal steel properties, linear service response, and the handout's symmetric gravity load case. The linear buckling factor characterizes first instability of the geometrically perfect model. Connection compliance, construction tolerances, and lateral crowd loading would require additional cases.

## AI use and verification record

The team supplied the V1 hand calculation and benchmark inputs. Codex implemented the 3D frame assembly, verification runner, response derivatives, optimization, and report graphics. The numerical checks compare the implementation against closed-form beam and column solutions, 3D rotation invariance, equilibrium, and independent finite differences. A review of the Hermite reconstruction found that the nodal-only deck check missed an interior deflection peak. V2 now includes a single-element case with zero displacement at both ends and a known maximum between them.
