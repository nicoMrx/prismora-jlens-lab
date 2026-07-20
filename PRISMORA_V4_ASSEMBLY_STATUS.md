# Prismora v4.2 assembly status

This branch is the first GPT-5.6-led assembly of the validated Prismora v4.1 interface with the existing Prismora engine.

## Working in this first pass

- standalone production Reader available at `/v4.html`;
- verified Build Week demo loaded from `/api/demo/build-week`;
- real prompt, output, generated tokens, measured layers, top candidates and candidate trajectory;
- explicit gaps for unmeasured layers;
- empty → pending → measured interface states;
- non-blocking Settings and account dialog;
- session settings and Neuronpedia connection test wired to the existing session API;
- local import of compatible `prismora.run/v2` JSON artifacts without an API key;
- Read / Explore / Control navigation preserves the existing deep-link paths;
- local Spectral, Albert Sans and Spline Sans Mono assets are used; no CDN dependency.

## Deliberately not implemented yet

- live Qwen conversation execution;
- broad conversion of arbitrary multi-file Neuronpedia export folders into RunArtifact v2;
- promotion of `/v4.html` to the default `/` route;
- full replacement of the existing Explorer and Control panels;
- packaged `prismora_lab/assets/web/v4.html` mirror.

## Acceptance path

1. Start Prismora locally.
2. Open `http://127.0.0.1:8001/v4.html`.
3. Continue without a key.
4. Click **Charger la démo vérifiée**.
5. Select the generated token and measured layers.
6. Verify the top candidates, trajectory and explicit layer gaps.
7. Test dark/light theme and session settings.

The old interface and scientific tools remain untouched and reachable through their existing routes.
