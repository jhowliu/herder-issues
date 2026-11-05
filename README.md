# herdr-issues

A [herdr](https://herdr.dev) plugin that shows the GitHub issues and PRs for your repo in a panel next to your agents.

- The panel opens to the right of the focused pane and shows the repo of that pane's folder.
- Descriptions and comments render as markdown.
- Mermaid diagrams are drawn as text. This is optional; see below.
- Press `p` on an issue to send it to the agent in the same tab.

## Requirements

- herdr 0.9.5 or later
- [`gh`](https://cli.github.com), logged in (`gh auth login`)
- Python 3.9 or later (standard library only)
- Optional: Node.js, for mermaid diagrams

## Install

```sh
git clone https://github.com/jhowliu/herder-issues.git ~/Developer/herdr-issues
herdr plugin link ~/Developer/herdr-issues
```

Add a key to `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+i"
type = "plugin_action"
command = "jhowliu.issues.toggle"
description = "GitHub issues/PRs panel"
```

Then run `herdr server reload-config`.

To draw mermaid diagrams, run:

```sh
cd ~/Developer/herdr-issues && npm install
```

Without it, mermaid blocks show as source.

## Keys

Press `prefix+i` to open the panel. Press it again, from any pane in the tab, to close it.

**List**

| Key | Action |
| --- | --- |
| `j` / `k` | Move down / up |
| `g` / `G` | Jump to top / bottom |
| `Enter` / `l` | Open the issue or PR |
| `Tab` | Switch between issues and PRs |
| `f` | Filter: open → closed → all |
| `r` | Refresh (it also refreshes every 60s) |
| `o` | Open in the browser |
| `p` | Send to the agent in this tab |
| `q` | Close the panel |

**Detail**

| Key | Action |
| --- | --- |
| `j` / `k` | Scroll one line |
| `l` / `h` | Scroll one page down / up (`space` / `b` also work) |
| `g` / `G` | Jump to top / bottom |
| `o` | Open in the browser |
| `p` | Send to the agent in this tab |
| `q` / `Esc` | Back to the list |

## Mermaid

Supported: flowchart, sequence, state, class and ER diagrams. Other types show as source.

If a diagram is too wide, the panel tries tighter spacing, then a top-down layout. If it still doesn't fit, it is cut at the panel's edge, and `o` opens the full diagram on GitHub.

## Future enhancements

- **Linear:** show your Linear issues in the same panel.
- **Jira:** show your Jira issues in the same panel.

## License

[MIT](LICENSE)
