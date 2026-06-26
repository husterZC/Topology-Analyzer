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

## Fresh Clone Tutorial

Clone the repository:

```sh
git clone https://github.com/husterZC/Topology-Analyzer.git
cd Topology-Analyzer
```

Build the repo-local Python environment and BookSim support:

```sh
make bootstrap
source .venv/bin/activate
```

Python 3.10 or newer is required. If the default `python3` is too old, choose an
interpreter explicitly:

```sh
make bootstrap BOOTSTRAP_PYTHON=python3.11
source .venv/bin/activate
```

Check that the CLI is available:

```sh
topoanalyzer --help
```

Generate a viewer for one system YAML:

```sh
topoanalyzer view examples/systems/lln/table/lln_4x4x5_table.yaml \
  --output-dir views/lln_4x4x5
```

The command writes:

```text
views/lln_4x4x5/
  index.html
  scene.json
  viewer.js
  style.css
  vendor/
```

Open `views/lln_4x4x5/index.html` in a browser.

## Example Systems

```sh
topoanalyzer view examples/systems/slimnoc/min/slimnoc_q5_p4_min.yaml \
  --output-dir views/slimnoc_q5_p4

topoanalyzer view examples/systems/slimnoc/figure7b/slimnoc_figure7b_snl_q9_p8_min.yaml \
  --output-dir views/slimnoc_figure7b_snl_q9_p8

topoanalyzer view examples/systems/ubmesh/dor/ubmesh_8x8_dor.yaml \
  --output-dir views/ubmesh_8x8

topoanalyzer view examples/systems/dragonfly/min/dragonfly_p2_a4_h2_min.yaml \
  --output-dir views/dragonfly_p2_a4_h2

topoanalyzer view examples/systems/hypercube/ecube/hypercube_d4_ecube.yaml \
  --output-dir views/hypercube_d4
```

## Viewer Controls

- Left drag: rotate.
- Mouse wheel: zoom.
- Right drag or `Shift` + drag: pan.
- Camera buttons: switch topology-specific views.
- Link checkboxes: show or hide link classes.
- Network links that share a coordinate plane are drawn with a small in-plane
  curve to reduce straight-line overlap.
- For SlimNoC Figure 7(b), `local cross links` are the shown intra-group
  vertical links and `inter-group cross links` are the omitted full-system
  connections.
- Labels toggle: show router and node labels.
- Terminal/injection nodes are rendered as small cuboids with attachment links
  back to their routers.
- Hover a router, node, or link: inspect metadata.
- Click a link: highlight the link and its two endpoints, greying out the rest.
- Click a router: highlight the router and its incident links, greying out the
  rest.
- Click the scene again: clear the highlight.

## Remote Server Use

For a remote cluster or server, either copy the generated viewer directory to a
local machine:

```sh
scp -r user@server:/path/to/Topology-Analyzer/views/lln_4x4x5 .
```

Then open `lln_4x4x5/index.html` locally.

Or serve it from the remote machine:

```sh
cd /path/to/Topology-Analyzer
python -m http.server 8000 --directory views/lln_4x4x5
```

Forward the port from the local machine:

```sh
ssh -L 8000:localhost:8000 user@server
```

Then open:

```text
http://localhost:8000
```

## Troubleshooting

If `topoanalyzer` is not found, activate the virtual environment:

```sh
source .venv/bin/activate
```

You can also run the CLI directly from source:

```sh
PYTHONPATH=src python -m topoanalyzer.cli view \
  examples/systems/lln/table/lln_4x4x5_table.yaml \
  --output-dir views/lln_4x4x5
```
