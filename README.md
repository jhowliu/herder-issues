# herdr-issues

A [herdr](https://herdr.dev) plugin that shows the GitHub issues and PRs for your repo in a panel next to your agents.

- The panel opens to the right of the focused pane and shows the repo of that pane's folder.
- Descriptions and comments render as markdown.
- Mermaid diagrams are drawn as text. This is optional; see below.
- Press `p` on an issue to send it to the agent in the same tab.
- Press `c` on an issue to run it with [codex-cage](https://github.com/jhowliu/codex-cage) in a background tab, and follow the run from the list.

## Requirements

- herdr 0.9.5 or later
- [`gh`](https://cli.github.com), logged in (`gh auth login`)
- Python 3.9 or later (standard library only)
- Optional: Node.js, for mermaid diagrams
- Optional: [codex-cage](https://github.com/jhowliu/codex-cage) on your `PATH`, and a `.codex-cage.yml` in the repo, for `c`

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
| `c` | Run the issue with codex-cage |
| `q` | Close the panel |

**Detail**

| Key | Action |
| --- | --- |
| `j` / `k` | Scroll one line |
| `l` / `h` | Scroll one page down / up (`space` / `b` also work) |
| `g` / `G` | Jump to top / bottom |
| `o` | Open in the browser |
| `p` | Send to the agent in this tab |
| `c` | Run the issue with codex-cage |
| `q` / `Esc` | Back to the list |

## Run issues with codex-cage

`c` hands an open issue to [codex-cage](https://github.com/jhowliu/codex-cage), which implements it in a Docker sandbox and opens a PR. The key shows in the footer only when `codex-cage` is on your `PATH` and the repo has a `.codex-cage.yml`.

1. The panel runs `codex-cage check` on the issue. If a `## Blocked by` issue is still open, or the config is invalid, the footer says why, and nothing starts.
2. The run starts in a new pane of a tab labelled `cage`. The tab is created in the background, so your view stays where it is. More runs split the cage tab, never your own panes.
3. While the run goes, herdr's agent list shows `codex-cage · cage` with the stage under it: `prepare`, `implement 2/3`, `verify`, `review`, `publish`, or `implement try 2`.
4. When it ends, the agent shows done with `PR opened`, or blocked with the failure code, such as `verify_failed`, and herdr shows a notification. The pane waits for Enter, then closes. The cage tab closes with its last pane.

The list shows each issue's latest run under its title:

| Mark | Meaning |
| --- | --- |
| `◐ implement 2/3` | Running, at this stage |
| `✓ PR opened` | Done; the detail view shows the PR link |
| `✗ verify_failed` | Failed with this code; run `codex-cage runs show <run-id>` in the repo for details |
| `✗ crashed` | codex-cage exited without a result; the cage pane shows why |
| `■ stopped` | Its pane was closed while it ran |

Runs always use codex-cage's Docker mode. codex-cage itself knows nothing about herdr: `herdr-issues run <issue-url>` runs in the cage pane, starts `codex-cage run`, and mirrors the events codex-cage writes to `.codex-cage/runs/<run-id>/events.ndjson`. The run's state lives in `.codex-cage/runs/delegate-<issue number>.json`. That is the same file codex-cage's delegate skill writes, so runs an agent starts with that skill show up in the list too.

## Mermaid

Supported: flowchart, sequence, state, class and ER diagrams. Other types show as source.

If a diagram is too wide, the panel tries tighter spacing, then a top-down layout. If it still doesn't fit, it is cut at the panel's edge, and `o` opens the full diagram on GitHub.

## Future enhancements

- **Linear:** show your Linear issues in the same panel.
- **Jira:** show your Jira issues in the same panel.

## Tests

```sh
python3 -m unittest discover tests
```

## License

[MIT](LICENSE)
