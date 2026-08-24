function prompt_command {
  local RED="\[\033[0;31m\]"
  local GREEN="\[\033[0;32m\]"
  local YELLOW="\[\033[1;33m\]"
  local GOLDENROD="\[\033[0;33m\]"
  local BLUE="\[\033[0;34m\]"
  local MAGENTA="\[\033[0;35m\]"
  local CYAN="\[\033[0;36m\]"
  local DARK_GRAY="\[\033[1;30m\]"
  local CRESET="\[\033[0m\]"

  local PROMPTCHAR='\\$'
  local PROMPTBRANCH=""
  local PROMPTNAME="${GREEN}\\u${BLUE}@${CYAN}\\h${CRESET} "

  # Single git call to retrieve branch and status simultaneously
  local git_output
  if git_output=$(git status --porcelain=v1 --branch 2>/dev/null); then
    PROMPTCHAR='±'
    local branch_line="${git_output%%$'\n'*}"
    local branch_name="${branch_line#\#\# }"
    branch_name="${branch_name%%...*}"

    local gitbang=""
    local gitcross=""
    local gitqmark=""

    # Pure bash pattern matching on porcelain status (no subshell/grep forks)
    while IFS= read -r line; do
      [[ -z "$line" || "$line" == "## "* ]] && continue
      local code="${line:0:2}"
      if [[ "${code:0:1}" =~ [MADRCU] ]]; then
        gitcross='+'
      fi
      if [[ "${code:1:1}" =~ [MDU] ]]; then
        gitbang='*'
      fi
      if [[ "$code" == "??" ]]; then
        gitqmark='?'
      fi
      [[ -n "$gitbang" && -n "$gitcross" && -n "$gitqmark" ]] && break
    done <<< "$git_output"

    PROMPTBRANCH="${BLUE}on $DARK_GRAY${branch_name}$CYAN$gitbang$gitcross$gitqmark$CRESET "
  fi

  local f="${TMPDIR:-/tmp/}/drush-env/drush-drupal-site-$$"
  local PROMPTDRUSH=""
  if [[ -f "$f" ]]; then
    PROMPTDRUSH="${BLUE}using $RED$(< "$f")$CRESET "
  fi

  export PS1="
${PROMPTNAME}${BLUE}at ${GOLDENROD}\w$CRESET ${PROMPTBRANCH}${PROMPTDRUSH}
${BLUE}${PROMPTCHAR}${CRESET} "
}

PROMPT_COMMAND=prompt_command
