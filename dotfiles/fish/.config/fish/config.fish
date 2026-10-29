fish_add_path $HOME/.local/bin

if status is-interactive
    set -g fish_greeting ""
    alias ls 'ls --color=auto'
    alias grep 'grep --color=auto'
    starship init fish | source
end
