"""
Knowledge graph exporter — reads video_metadata from Qdrant and produces:
  graph.json   — nodes (videos) + edges (shared tags)
  graph.html   — self-contained D3.js force-directed viewer, no server needed

Usage:
    python graph.py
    python graph.py --output sync/output/graph.json
    python graph.py --qdrant-host localhost:6333 --output sync/output/graph.json
"""

import argparse
import json
import os
import sys

from qdrant_client import QdrantClient

META_COLLECTION = "video_metadata"

SENTIMENT_COLOURS = {
    "positive": "#4caf50",
    "neutral": "#90a4ae",
    "negative": "#f44336",
}
DEFAULT_COLOUR = "#78909c"

# graph_template.html lives alongside this script
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "graph_template.html")


def _parse_host_port(addr: str, default_port: int):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def load_metadata(qdrant: QdrantClient) -> list[dict]:
    """Scroll all points from the video_metadata collection."""
    points = []
    offset = None
    while True:
        result, next_offset = qdrant.scroll(
            collection_name=META_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(result)
        if next_offset is None:
            break
        offset = next_offset
    return [p.payload for p in points]


def build_graph(records: list[dict]) -> dict:
    """Build nodes and edges from metadata records."""
    nodes = []
    for rec in records:
        file_name = rec.get("file", "unknown")
        node_id = os.path.basename(file_name)
        sentiment = rec.get("sentiment_label", "neutral")
        nodes.append({
            "id": node_id,
            "label": rec.get("title", node_id),
            "file": file_name,
            "lang": rec.get("lang", ""),
            "uploaded_by": rec.get("uploaded_by", ""),
            "tags": rec.get("tags", []),
            "sentiment_label": sentiment,
            "sentiment_score": rec.get("sentiment_score", 0.0),
            "colour": SENTIMENT_COLOURS.get(sentiment, DEFAULT_COLOUR),
        })

    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            shared = set(nodes[i]["tags"]) & set(nodes[j]["tags"])
            if shared:
                edges.append({
                    "source": nodes[i]["id"],
                    "target": nodes[j]["id"],
                    "weight": len(shared),
                    "shared_tags": sorted(shared),
                })

    return {"nodes": nodes, "edges": edges}


def write_json(graph: dict, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print(f"graph.json written → {output_path}")


def write_html(graph: dict, html_path: str):
    """Render graph_template.html with inline graph data and filter options."""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    langs = sorted({n["lang"] for n in graph["nodes"] if n["lang"]})
    uploaders = sorted({n["uploaded_by"] for n in graph["nodes"] if n["uploaded_by"]})

    lang_options = "".join(f'<option value="{l}">{l}</option>' for l in langs)
    uploader_options = "".join(f'<option value="{u}">{u}</option>' for u in uploaders)

    html = (
        template
        .replace("{{GRAPH_JSON}}", json.dumps(graph, ensure_ascii=False))
        .replace("{{LANG_OPTIONS}}", lang_options)
        .replace("{{UPLOADER_OPTIONS}}", uploader_options)
    )

    os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"graph.html written  → {html_path}")


def main():
    parser = argparse.ArgumentParser(description="Export knowledge graph from video_metadata.")
    parser.add_argument("--output", default="sync/output/graph.json",
                        help="Output path for graph.json (default: sync/output/graph.json)")
    parser.add_argument("--qdrant-host", default="localhost:6333",
                        help="Qdrant host:port (default: localhost:6333)")
    args = parser.parse_args()

    q_host, q_port = _parse_host_port(args.qdrant_host, 6333)
    qdrant = QdrantClient(host=q_host, port=q_port)

    print("Loading video_metadata from Qdrant…")
    try:
        records = load_metadata(qdrant)
    except Exception as exc:
        print(f"ERROR: could not read from Qdrant ({exc})", file=sys.stderr)
        sys.exit(1)

    if not records:
        print("WARNING: no records found in video_metadata — graph will be empty.")

    print(f"  {len(records)} videos loaded.")
    graph = build_graph(records)

    json_path = args.output
    html_path = os.path.splitext(json_path)[0] + ".html"

    write_json(graph, json_path)
    write_html(graph, html_path)

    print(f"\nNodes : {len(graph['nodes'])}")
    print(f"Edges : {len(graph['edges'])}")


if __name__ == "__main__":
    main()
