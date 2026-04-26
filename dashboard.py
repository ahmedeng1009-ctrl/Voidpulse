"""
VoidPulse Analytics Dashboard — Graphical UI
Opens a dark-themed window with charts and a video stats table.

Usage:
    python dashboard.py
    python dashboard.py --offline    # use cached data only, no API call
"""

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

# ── Dark theme palette ────────────────────────────────────────────────────────

BG       = "#0a0a0f"
BG2      = "#12121a"
BG3      = "#1c1c28"
ACCENT   = "#cc2222"
ACCENT2  = "#ff4444"
TEXT     = "#e8e8e8"
TEXT_DIM = "#888899"
GREEN    = "#44cc66"
GOLD     = "#ffcc44"

FONT_FAMILY = "Segoe UI"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_local_data() -> list[dict]:
    log_file = Path("metadata/uploaded_videos.json")
    if not log_file.exists():
        return []
    try:
        return json.loads(log_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def fetch_live_stats(log: list[dict]) -> list[dict]:
    """Pull live stats from YouTube API via analytics.py helpers."""
    sys.path.insert(0, str(Path(__file__).parent))
    from analytics import fetch_video_stats

    video_ids = [e["id"] for e in log]
    if not video_ids:
        return []

    stats    = fetch_video_stats(video_ids)
    log_map  = {e["id"]: e for e in log}
    for s in stats:
        s["topic"]       = log_map.get(s["id"], {}).get("topic", "Unknown")
        s["uploaded_at"] = log_map.get(s["id"], {}).get("uploaded_at", "")[:10]
    stats.sort(key=lambda x: x["views"], reverse=True)
    return stats


def merge_log_only(log: list[dict]) -> list[dict]:
    """Build display rows from local log only (no API call)."""
    rows = []
    for e in log:
        rows.append({
            "id":          e["id"],
            "title":       e.get("topic", "Unknown"),
            "topic":       e.get("topic", "Unknown"),
            "uploaded_at": e.get("uploaded_at", "")[:10],
            "views":       e.get("views", 0),
            "likes":       e.get("likes", 0),
            "comments":    e.get("comments", 0),
            "url":         e.get("url", f"https://youtu.be/{e['id']}"),
        })
    rows.sort(key=lambda x: x["views"], reverse=True)
    return rows


# ── GUI ───────────────────────────────────────────────────────────────────────

def build_gui(stats: list[dict], offline: bool):
    try:
        import tkinter as tk
        from tkinter import ttk, font as tkfont
    except ImportError:
        print("tkinter not available.")
        sys.exit(1)

    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        HAS_MATPLOTLIB = True
    except ImportError:
        HAS_MATPLOTLIB = False

    # ── Root window ───────────────────────────────────────────────────────────
    root = tk.Tk()
    root.title("VoidPulse Analytics Dashboard")
    root.configure(bg=BG)
    root.geometry("1100x780")
    root.minsize(900, 600)

    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    # ── Helper widgets ────────────────────────────────────────────────────────
    def label(parent, text, size=11, color=TEXT, bold=False, **kw):
        weight = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=kw.pop("bg", BG2),
                        fg=color, font=(FONT_FAMILY, size, weight), **kw)

    def frame(parent, bg=BG2, **kw):
        return tk.Frame(parent, bg=bg, **kw)

    # ── Title bar ─────────────────────────────────────────────────────────────
    title_bar = frame(root, bg=BG)
    title_bar.pack(fill="x", padx=16, pady=(14, 4))

    label(title_bar, "▶  VOIDPULSE", size=20, color=ACCENT, bold=True, bg=BG).pack(side="left")
    label(title_bar, "Analytics Dashboard", size=13, color=TEXT_DIM, bg=BG).pack(side="left", padx=10)

    mode_str = "OFFLINE" if offline else "LIVE"
    mode_col = TEXT_DIM if offline else GREEN
    label(title_bar, f"● {mode_str}", size=10, color=mode_col, bg=BG).pack(side="right")

    ts = datetime.now().strftime("%Y-%m-%d  %H:%M")
    label(title_bar, ts, size=10, color=TEXT_DIM, bg=BG).pack(side="right", padx=12)

    # ── Summary cards ─────────────────────────────────────────────────────────
    total_views    = sum(s["views"]    for s in stats)
    total_likes    = sum(s["likes"]    for s in stats)
    total_comments = sum(s["comments"] for s in stats)
    avg_views      = total_views // max(len(stats), 1)

    cards_row = frame(root, bg=BG)
    cards_row.pack(fill="x", padx=16, pady=6)

    card_data = [
        ("VIDEOS",    str(len(stats)),          TEXT),
        ("VIEWS",     f"{total_views:,}",        ACCENT2),
        ("LIKES",     f"{total_likes:,}",        GOLD),
        ("COMMENTS",  f"{total_comments:,}",     TEXT),
        ("AVG VIEWS", f"{avg_views:,}",          GREEN),
    ]

    for title, value, col in card_data:
        card = frame(cards_row, bg=BG3)
        card.pack(side="left", fill="x", expand=True, padx=4, pady=2, ipadx=10, ipady=8)
        label(card, title, size=8,  color=TEXT_DIM, bold=True, bg=BG3).pack()
        label(card, value, size=18, color=col,      bold=True, bg=BG3).pack()

    # ── Separator ─────────────────────────────────────────────────────────────
    sep = tk.Frame(root, bg=ACCENT, height=1)
    sep.pack(fill="x", padx=16, pady=4)

    # ── Main content (chart left, table right) ────────────────────────────────
    content = frame(root, bg=BG)
    content.pack(fill="both", expand=True, padx=16, pady=4)

    # ── Bar chart ─────────────────────────────────────────────────────────────
    if HAS_MATPLOTLIB and stats:
        chart_frame = frame(content, bg=BG2)
        chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        labels = [s["topic"][:22] + "…" if len(s["topic"]) > 22 else s["topic"]
                  for s in stats]
        views  = [s["views"] for s in stats]
        colors = [ACCENT if i == 0 else "#6b1111" for i in range(len(views))]

        fig, ax = plt.subplots(figsize=(5, 4))
        fig.patch.set_facecolor(BG2)
        ax.set_facecolor(BG3)

        max_views = max(views) if any(v > 0 for v in views) else 1

        if max_views == 1 and all(v == 0 for v in views):
            # All zeros — show placeholder message
            ax.text(0.5, 0.5, "No view data yet\nCheck back after videos go live",
                    transform=ax.transAxes, ha="center", va="center",
                    color=TEXT_DIM, fontsize=10, linespacing=1.8)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
        else:
            bars = ax.barh(range(len(labels)), views, color=colors, height=0.6)

            for bar, v in zip(bars, views):
                ax.text(bar.get_width() + max_views * 0.01,
                        bar.get_y() + bar.get_height() / 2,
                        f"{v:,}", va="center", ha="left",
                        color=TEXT, fontsize=8, fontfamily="monospace")

            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, color=TEXT, fontsize=8)
            ax.tick_params(axis="x", colors=TEXT_DIM, labelsize=8)
            ax.set_xlabel("Views", color=TEXT_DIM, fontsize=9)
            ax.set_xlim(0, max_views * 1.15)
            for spine in ax.spines.values():
                spine.set_edgecolor(BG3)
            ax.xaxis.grid(True, color=BG, linewidth=0.5, alpha=0.5)
            ax.set_axisbelow(True)

        ax.set_title("Views per Video", color=TEXT, fontsize=10, pad=8)
        fig.tight_layout(pad=1.5)

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # ── Table ─────────────────────────────────────────────────────────────────
    table_frame = frame(content, bg=BG2)
    table_frame.pack(side="right", fill="both", expand=True)

    label(table_frame, "All Videos", size=10, color=TEXT, bold=True,
          bg=BG2).pack(anchor="w", padx=8, pady=(6, 2))

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("VP.Treeview",
                    background=BG3, foreground=TEXT, fieldbackground=BG3,
                    rowheight=28, font=(FONT_FAMILY, 9),
                    borderwidth=0, relief="flat")
    style.configure("VP.Treeview.Heading",
                    background=BG, foreground=ACCENT2,
                    font=(FONT_FAMILY, 9, "bold"), relief="flat")
    style.map("VP.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

    cols = ("rank", "topic", "views", "likes", "comments", "date")
    tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                        style="VP.Treeview", height=12)

    col_cfg = [
        ("rank",     "#",        40,  "center"),
        ("topic",    "Topic",   220,  "w"),
        ("views",    "Views",    70,  "e"),
        ("likes",    "Likes",    60,  "e"),
        ("comments", "Cmts",     50,  "e"),
        ("date",     "Date",     80,  "center"),
    ]
    for cid, heading, width, anchor in col_cfg:
        tree.heading(cid, text=heading)
        tree.column(cid, width=width, anchor=anchor, stretch=(cid == "topic"))

    for i, s in enumerate(stats, 1):
        tree.insert("", "end", iid=s["id"], values=(
            f"#{i}",
            s["topic"][:35],
            f"{s['views']:,}",
            f"{s['likes']:,}",
            f"{s['comments']:,}",
            s["uploaded_at"],
        ))

    # Alternating row colors
    for i, item in enumerate(tree.get_children()):
        bg_row = BG3 if i % 2 == 0 else BG2
        tree.tag_configure(f"row{i}", background=bg_row)
        tree.item(item, tags=(f"row{i}",))

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
    scrollbar.pack(side="right", fill="y", pady=4)

    # Double-click to open video in browser
    def on_double_click(event):
        sel = tree.selection()
        if sel:
            video_id = sel[0]
            webbrowser.open(f"https://youtu.be/{video_id}")

    tree.bind("<Double-1>", on_double_click)

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = frame(root, bg=BG)
    bottom.pack(fill="x", padx=16, pady=(4, 10))

    hint = "Double-click a row to open video  ·  " + ("Showing cached data" if offline else "Live data from YouTube API")
    label(bottom, hint, size=9, color=TEXT_DIM, bg=BG).pack(side="left")

    def on_refresh():
        root.destroy()
        main_run(offline=False)

    refresh_btn = tk.Button(
        bottom, text="⟳  Refresh", command=on_refresh,
        bg=ACCENT, fg="white", font=(FONT_FAMILY, 9, "bold"),
        relief="flat", padx=12, pady=4, cursor="hand2",
        activebackground=ACCENT2, activeforeground="white",
    )
    refresh_btn.pack(side="right")

    root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────

def main_run(offline: bool):
    log = load_local_data()

    if not log:
        print("No uploaded videos tracked yet.")
        print("Run run_pipeline.py first to produce and upload videos.")
        sys.exit(0)

    if offline:
        print("Loading cached data (offline mode)...")
        stats = merge_log_only(log)
    else:
        print(f"Fetching live stats for {len(log)} video(s)...")
        try:
            stats = fetch_live_stats(log)
        except Exception as e:
            print(f"YouTube API error: {e}")
            print("Falling back to cached data...")
            stats = merge_log_only(log)

    if not stats:
        print("No stats available.")
        sys.exit(0)

    build_gui(stats, offline)


def main():
    parser = argparse.ArgumentParser(description="VoidPulse Analytics Dashboard")
    parser.add_argument("--offline", action="store_true",
                        help="Use cached data only, skip YouTube API call")
    args = parser.parse_args()
    main_run(offline=args.offline)


if __name__ == "__main__":
    main()
