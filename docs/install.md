# Install

## Requirements

### The gh CLI

gh-inbox is built on the [`gh` CLI](https://cli.github.com),
the official GitHub command-line tool.
The app does not connect to GitHub itself.
In the background, it runs `gh api` for each request to GitHub.
`gh` sends the request with your GitHub login.
The app does not keep a GitHub token of its own.

The app does not work without `gh`.
Install and log in to `gh` before you install gh-inbox.

1. Install `gh` for your system. Follow the
   [installation instructions](https://github.com/cli/cli#installation).
2. Log in with your own GitHub account:

   ```bash
   gh auth login
   ```

3. Make sure that the login works:

   ```bash
   gh auth status
   ```

### Systems

| | Linux | macOS | Windows |
| :-- | :-- | :-- | :-- |
| Status | Tested (Ubuntu, GNOME) | Not tested | Tested (Windows 11) |
| Python | 3.10 or later | 3.10 or later | 3.10 or later |
| `gh` CLI | Yes | Yes | Yes |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Install from the source | Install from the source | Install from the source |
| Pop-ups | `notify-send` | Built in | Built in |

The executable needs no Python and no `uv`. Only the install from the source needs them.

## Installation

Install gh-inbox in one of the two ways below.

### Download the executable

This way needs no Python.

=== "Linux"

    1. Download `gh-inbox-linux` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    2. Make the file executable:

        ```bash
        chmod +x gh-inbox-linux
        ```

    3. Start the app:

        ```bash
        ./gh-inbox-linux web
        ```

=== "macOS"

    1. Download `gh-inbox-macos` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    2. Make the file executable:

        ```bash
        chmod +x gh-inbox-macos
        ```

    3. Start the app:

        ```bash
        ./gh-inbox-macos web
        ```

    The file has no signature. macOS shows a warning the first time.
    Right-click the file and select **Open**.

=== "Windows"

    1. Download `gh-inbox-windows.exe` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    2. Start the app:

        ```powershell
        .\gh-inbox-windows.exe web
        ```

    The file has no signature. Windows shows a warning the first time.
    Click **More info**, then **Run anyway**.

### Install from the source

=== "Linux"

    1. Get the code:

        ```bash
        git clone https://github.com/florence-bockting/gh-inbox.git
        cd gh-inbox
        ```

    2. Install the app with `uv`. This also installs Flask and Textual.

        ```bash
        uv tool install .
        ```

    3. Start the app:

        ```bash
        gh-inbox web
        ```

=== "macOS"

    1. Get the code:

        ```bash
        git clone https://github.com/florence-bockting/gh-inbox.git
        cd gh-inbox
        ```

    2. Install the app with `uv`. This also installs Flask and Textual.

        ```bash
        uv tool install .
        ```

    3. Start the app:

        ```bash
        gh-inbox web
        ```

=== "Windows"

    1. Get the code:

        ```powershell
        git clone https://github.com/florence-bockting/gh-inbox.git
        cd gh-inbox
        ```

    2. Install the app with `uv`. This also installs Flask and Textual.

        ```powershell
        uv tool install .
        ```

    3. Start the app:

        ```powershell
        gh-inbox web
        ```

`uv` installs the app in its own environment. It puts the `gh-inbox` command in your `PATH`.
If your shell does not find `gh-inbox`, run `uv tool update-shell`. Then open a new terminal.
The install is a copy of the code. A later change in the folder has no effect on the command.
To use a new release, see [Update an install from the source](#update-an-install-from-the-source).
To change the code, see [Run your changes](developers.md#run-your-changes).

The command starts the [daemon](usage.md#basic-commands) and opens http://127.0.0.1:8765 in your browser.
The daemon runs in the background. You can close the terminal.
To stop the daemon, click **Stop daemon** on the web page, or run `gh-inbox stop`.

Then set up the app in the browser. For the terminal UI, see [Start the app](usage.md#start-the-app).

1. Open the **Repos** tab ([how your inbox is organized](usage.md#how-your-inbox-is-organized)). Click **Load my GitHub repos**, or type `owner/repo`.
   Then select the repos to watch.

2. Click **Sync now** and wait for the updates to appear.

## Update to a new release

Each new release appears on the
[releases page](https://github.com/florence-bockting/gh-inbox/releases).
Update the app in the same way that you installed it.

!!! note
    The daemon keeps the old version until you restart it.

### Update the executable

=== "Linux"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `gh-inbox-linux` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Make the file executable:

        ```bash
        chmod +x gh-inbox-linux
        ```

    5. Start the app again:

        ```bash
        ./gh-inbox-linux web
        ```

=== "macOS"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `gh-inbox-macos` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Make the file executable:

        ```bash
        chmod +x gh-inbox-macos
        ```

    5. Start the app again:

        ```bash
        ./gh-inbox-macos web
        ```

=== "Windows"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `gh-inbox-windows.exe` from the
       [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Start the app again:

        ```powershell
        .\gh-inbox-windows.exe web
        ```

### Update an install from the source

=== "Linux"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Get the list of releases:

        ```bash
        git fetch --tags
        ```

    3. Change to the new release. Replace `v0.1.0` with the release name:

        ```bash
        git checkout v0.1.0
        ```

    4. Install again. A new release can add dependencies:

        ```bash
        uv tool install --force .
        ```

    5. Start the app again:

        ```bash
        gh-inbox web
        ```

=== "macOS"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Get the list of releases:

        ```bash
        git fetch --tags
        ```

    3. Change to the new release. Replace `v0.1.0` with the release name:

        ```bash
        git checkout v0.1.0
        ```

    4. Install again. A new release can add dependencies:

        ```bash
        uv tool install --force .
        ```

    5. Start the app again:

        ```bash
        gh-inbox web
        ```

=== "Windows"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Get the list of releases:

        ```powershell
        git fetch --tags
        ```

    3. Change to the new release. Replace `v0.1.0` with the release name:

        ```powershell
        git checkout v0.1.0
        ```

    4. Install again. A new release can add dependencies:

        ```powershell
        uv tool install --force .
        ```

    5. Start the app again:

        ```powershell
        gh-inbox web
        ```

!!! tip "Get the newest code before a release"
    The newest code can contain changes that are not in a release yet.
    To get it, use these commands in place of steps 2 and 3:

    ```bash
    git checkout main
    git pull
    ```
