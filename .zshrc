# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="robbyrussell"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(git aliases zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
cd ~/work

# History settings
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY         # Share history across shell sessions
setopt HIST_IGNORE_DUPS      # Do not record duplicate entries

# Enable auto-completion
autoload -U compinit && compinit

# Useful Aliases
alias o='open'
alias cl='clear'
alias ls='ls --color=auto' 2>/dev/null || alias ls='ls -G'
alias ll='ls -la'
alias gs='git s'
alias vs='code'
alias vsc='code'

# User local binaries & LANDO Path
export PATH="$HOME/.local/bin:/home/mike/.lando/bin:$PATH";

# Aliases for Lando & Drush
alias ldrush='lando drush'
alias ld='lando drush'

# VPN aliases
alias vpn-on='openvpn3 session-start --config mnielson'
alias vpn-off='openvpn3 session-manage --disconnect -c mnielson'

# Antigravity (AGY) Aliases & Helpers
alias ag="agy"

agask() {
  agy --prompt "$*"
}

agadd() {
  agy /add-dir "$(pwd)"
}

agreview() {
  git diff | agy "Review these changes for potential bugs or code quality improvements"
}

gcai() {
  local ticket=""
  local -a context_args=()
  local is_first=1
  local ticket_pattern="^(\\[.+\\]|[A-Za-z0-9_]+-[A-Za-z0-9_]+|#?[0-9]+|.+:)$"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -t|--ticket)
        if [[ -n "$2" && "$2" != -* ]]; then
          ticket="$2"
          shift 2
        else
          echo "Error: -t/--ticket requires a ticket number argument."
          return 1
        fi
        ;;
      -t=*|--ticket=*)
        ticket="${1#*=}"
        shift
        ;;
      -m|--message|-c|--context)
        if [[ -n "$2" ]]; then
          context_args+=("$2")
          shift 2
        else
          echo "Error: $1 requires an argument."
          return 1
        fi
        ;;
      -m=*|--message=*|-c=*|--context=*)
        context_args+=("${1#*=}")
        shift
        ;;
      -h|--help)
        echo "Usage: gcai [-t|--ticket <ticket>] [-m|--message <context>] [<context/ticket>...]"
        echo "Generate an AI commit message for staged changes with optional ticket number and context."
        return 0
        ;;
      *)
        if [[ -z "$ticket" && $is_first -eq 1 ]]; then
          if [[ "$1" =~ $ticket_pattern ]]; then
            ticket="$1"
          elif [[ $# -eq 1 && ! "$1" =~ [[:space:]] ]]; then
            ticket="$1"
          else
            context_args+=("$1")
          fi
        else
          context_args+=("$1")
        fi
        shift
        ;;
    esac
    is_first=0
  done

  local context="${context_args[*]}"

  # Resolve the git repo root so agy runs with the correct context.
  local repo_root
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
  if [[ -z "$repo_root" ]]; then
    echo "Not inside a git repository."
    return 1
  fi

  # Bail early if nothing is staged.
  if git diff --cached --quiet 2>/dev/null; then
    echo "No staged changes found. Stage files with 'git add' first."
    return 1
  fi

  if [[ -n "$ticket" && -n "$context" ]]; then
    echo "Generating commit message for ticket $ticket with context: \"$context\"..."
  elif [[ -n "$ticket" ]]; then
    echo "Generating commit message for ticket: $ticket..."
  elif [[ -n "$context" ]]; then
    echo "Generating commit message with context: \"$context\"..."
  else
    echo "Generating commit message from staged changes..."
  fi

  local difffile msg
  difffile=$(mktemp /tmp/gcai-diff-XXXXXX.patch)
  git diff --cached > "$difffile"

  local prompt="Read the git diff at $difffile and write a commit message using the Conventional Commits 1.0.0 specification.

Format: <type>[optional scope]: <description>

Rules:
- type MUST be one of: feat, fix, build, chore, ci, docs, style, refactor, perf, test
- scope is optional and describes the section of the codebase (e.g. parser, api)
- description MUST be a concise imperative summary (lowercase, no period)
- Do NOT include a body or footer unless the change is a BREAKING CHANGE
- Do NOT include the ticket/issue prefix in your output as it will be prepended automatically
- Output ONLY the commit message — no quotes, backticks, markdown, or explanation"

  if [[ -n "$context" ]]; then
    prompt+=$'\n\n'"User instructions / context to incorporate in the commit message:"$'\n'"$context"
  fi

  # Write the diff to a file so agy can read it with its tools —
  # inline embedding breaks on special chars and agy ignores piped stdin.
  msg=$(agy --print "$prompt")
  rm -f "$difffile"

  if [[ -z "$msg" ]]; then
    echo "Failed to generate a commit message."
    return 1
  fi

  # Clean up any potential markdown formatting or quotes from AI response
  msg=$(echo "$msg" | sed -e 's/^```[a-zA-Z]*//' -e 's/```$//' -e '/^[[:space:]]*$/d' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')

  if [[ -n "$ticket" ]]; then
    if [[ "$msg" != *"$ticket"* ]]; then
      if [[ "$ticket" == \[*\] ]] || [[ "$ticket" == *: ]]; then
        msg="$ticket $msg"
      else
        msg="[$ticket] $msg"
      fi
    fi
  fi

  echo "\n\033[1;36mSuggested commit message:\033[0m"
  echo "\033[0;33m$msg\033[0m\n"

  local confirm
  read "confirm?Commit with this message? [y]es / [e]dit / [n]o: "

  case "$confirm" in
    y|Y|yes)
      git commit -m "$msg"
      ;;
    e|E|edit)
      local tmpfile
      tmpfile=$(mktemp /tmp/gcai-msg-XXXXXX)
      echo "$msg" > "$tmpfile"
      ${EDITOR:-vim} "$tmpfile"
      local edited_msg
      edited_msg=$(cat "$tmpfile")
      rm -f "$tmpfile"
      if [[ -n "$edited_msg" ]]; then
        git commit -m "$edited_msg"
      else
        echo "Empty message — commit aborted."
        return 1
      fi
      ;;
    *)
      echo "Commit aborted."
      return 1
      ;;
  esac
}

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
