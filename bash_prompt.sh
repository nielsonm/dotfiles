function prompt_command {
local RED="\[\033[0;31m\]"
local GREEN="\[\033[0;32m\]"
local YELLOW="\[\033[0;33m\]"
local BLUE="\[\033[0;34m\]"
local MAGENTA="\[\033[0;35m\]"
local CYAN="\[\033[0;36m\]"
local CRESET="\[\033[0m\]"

if git branch >/dev/null 2>/dev/null; then
  local PROMPTCHAR='±'
else
  local PROMPTCHAR='\\$'
fi

local PROMPTNAME="${GREEN}\\u${BLUE}@${CYAN}\\h${CRESET} "

ref=$(git symbolic-ref HEAD 2> /dev/null)
if [[ -n $ref ]]; then
  gitstat=$(git status 2>/dev/null | grep '^\(Untracked\|Changes\|Changed but not updated:\)')
  if [[ $(echo ${gitstat} | grep -c "^\(Changes to be committed:\|Changes not staged for commit:\)$") > 0 ]]; then
    local gitbang='!'
  fi
  if [[ $(echo ${gitstat} | grep -c "^\(Untracked files:\|Changed but not updated:\)$") > 0 ]]; then
    local gitqmark='?'
  fi
  local PROMPTBRANCH="${BLUE}on$MAGENTA$(__git_ps1)$CYAN$gitbang$gitqmark$CRESET "
fi

f="${TMPDIR:-/tmp/}/drush-env/drush-drupal-site-$$"
if [ -f $f ]; then
  local PROMPTDRUSH="${BLUE}using $RED$(cat "$f")$CRESET "
fi

export PS1="
${PROMPTNAME}${BLUE}at ${YELLOW}\w$CRESET ${PROMPTBRANCH}${PROMPTDRUSH}
${BLUE}${PROMPTCHAR}${CRESET} "
}

PROMPT_COMMAND=prompt_command
