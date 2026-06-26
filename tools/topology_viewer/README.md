# Topology Viewer Assets

This folder contains the static Three.js viewer used by:

```sh
topoanalyzer view <system.yaml> --output-dir views/<name>
```

The CLI writes `scene.json`, embeds the same scene into `index.html`, and copies
`viewer.js`, `style.css`, and `vendor/` into the output directory. The generated
`index.html` can be opened directly in a browser.

The viewer uses the repo-local Three.js runtime file under `vendor/three/`.
The generated scene data is local and self-contained.
