# herdr-issues

A [herdr](https://herdr.dev) plugin that shows the GitHub issues and PRs for your repo in a panel next to your agents.

- The panel opens to the right of the focused pane and shows the repo of that pane's folder.
- Descriptions and comments render as markdown.
- Mermaid diagrams are drawn as text. This is optional; see below.
- Press `p` on an issue to send it to the agent in the same tab.
- Press `c` on an issue to run it with [agent-cage](https://github.com/jhowliu/agent-cage) in a background tab, and follow the run from the list.

## Requirements

- herdr 0.9.5 or later
- [`gh`](https://cli.github.com), logged in (`gh auth login`)
- Python 3.9 or later (standard library only)
- Optional: Node.js, for mermaid diagrams
- Optional: [agent-cage](https://github.com/jhowliu/agent-cage) on your `PATH`, and a `.agent-cage.yml` in the repo, for `c`. Run state in the list needs a agent-cage with `runs list --json`.

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

The panel opens to the right of the focused pane. Beside a pane narrower than 120 columns it opens zoomed, filling the tab, so the panel is never squeezed; press `z` to un-zoom it. Below 46 columns the list wraps each title onto two lines and drops the age column, and the footer shortens to the keys that fit. `?` lists every key.

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
| `c` | Run the issue with agent-cage |
| `z` | Zoom the panel to fill the tab, or un-zoom it |
| `?` | List the keys (any key closes it) |
| `q` | Close the panel |

**Detail**

| Key | Action |
| --- | --- |
| `j` / `k` | Scroll one line |
| `l` / `h` | Scroll one page down / up (`space` / `b` also work) |
| `g` / `G` | Jump to top / bottom |
| `o` | Open in the browser |
| `p` | Send to the agent in this tab |
| `c` | Run the issue with agent-cage |
| `z` | Zoom the panel to fill the tab, or un-zoom it |
| `?` | List the keys (any key closes it) |
| `q` / `Esc` | Back to the list |

## Run issues with agent-cage

`c` hands an open issue to [agent-cage](https://github.com/jhowliu/agent-cage), which implements it in a Docker sandbox and opens a PR. The key shows in the footer only when `agent-cage` is on your `PATH` and the repo has a `.agent-cage.yml`.

1. The panel runs `agent-cage check` on the issue. If a `## Blocked by` issue is still open, or the config is invalid, the footer says why, and nothing starts.
2. The run starts in a new pane of a tab labelled `cage`. The tab is created in the background, so your view stays where it is. More runs split the cage tab, never your own panes.
3. While the run goes, herdr's agent list shows `agent-cage · cage` with the stage under it: `prepare`, `implement 2/3`, `verify`, `review`, `publish`, or `implement try 2`.
4. When it ends, the agent shows done with `PR opened`, or blocked with the failure code, such as `verify_failed`, and herdr shows a notification. The pane waits for Enter, then closes. The cage tab closes with its last pane.

The list shows each issue's latest run under its title. It reads `agent-cage runs list --json` every 2 seconds, so it shows every run in the repo, including runs an agent starts with agent-cage's `agent-cage-planner` skill:

| Mark | Meaning |
| --- | --- |
| `◐ starting` | You pressed `c`, and agent-cage has not recorded the run yet |
| `◐ implementing` | Running, with agent-cage's status: `cloning`, `setup`, `implementing`, `verifying`, `reviewing`, `creating pr` |
| `✓ PR opened` | Done; the detail view shows the PR link |
| `✗ verify_failed` | Failed with this code; run `agent-cage runs show <run-id>` in the repo for details |
| `■ interrupted` | It never finished, and its process is gone, for example because its pane was closed |

Runs always use agent-cage's Docker mode. agent-cage itself knows nothing about herdr: `herdr-issues run <issue-url>` runs in the cage pane, starts `agent-cage run`, and mirrors the events agent-cage writes to `.agent-cage/runs/<run-id>/events.ndjson`. If agent-cage exits without a result, the cage pane and herdr's agent list show `crashed`.

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
