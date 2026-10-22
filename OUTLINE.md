cortex: a command cheatsheet manager/merger/sorter

- scrape various cheatsheet repos for markdown files
  - cht.sh, tldr, tealdeer, navi, etc
  - also scrape from certain websites: devhints, cheatsheets.zip, etc
  - download it all into cache folder
  - keep track of all the sources and generate a list of all the commands
- merge them all into one folder
  - only extract commands that exist on the system
  - they should all be transformed into the same format (one comment line per command)
  - categorize the commands by type of function it performs

```
# Quickly extract a single frame from a video at time mm:ss and save it as a 128x128 resolution image:
ffmpeg -ss mm:ss -i video.mp4 -frames 1 -s 128x128 -f image2 image.png
```

- combine them from the different sources, remove redundancies, and save them as a single md file
- create a config file if not exists, ~/.config/cortex.toml (or whatever extension makes sense)
- this will be used to determine the sources and some of the behavior
- other config options:
  - default display (stdout, fzf, or tmux split) (these should also be commandline switches)
  - syntax highlighting command (default bat)
- allow custom additions (that won't be overwritten)
- allow custom removals (that will be remembered at next sync)
- allow listing all commands (with same display options)
- allow quick search (with same display options)
- create zsh widget that looks for the command from the prompt and searches for it
- i want the program to be visually pleasing (colors, formatting, alignment, etc)
- if selected from fzf replace the prompt with the command

- display:
  - it might be easier to leave the display option as a config value/command line switch that holds a command string
  - i want to be able to display it as a tmux split, pop, fzf, fzf-tmux split, or fzf-tmux popup
  - if a tmux split is used, I want focus to remain on prompt pane, and a keyboard shortcut, preferbly  '<M-{>' to close
    the command display pane
- eventually i would like to show more than just bash commands, but we'll start with that for now
