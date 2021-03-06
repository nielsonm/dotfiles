# ~/.bashrc: executed by bash(1) for non-login shells.
# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
# for examples

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# don't put duplicate lines in the history. See bash(1) for more options
# ... or force ignoredups and ignorespace
HISTCONTROL=ignoredups:ignorespace

# append to the history file, don't overwrite it
shopt -s histappend

# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)
HISTSIZE=1000000
HISTFILESIZE=2000000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "want" color)
case "$TERM" in
    xterm-color) color_prompt=yes;;
esac

# uncomment for a colored prompt, if the terminal has the capability; turned
# off by default to not distract the user: the focus in a terminal window
# should be on the output of commands, not on the prompt
#force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
	# We have color support; assume it's compliant with Ecma-48
	# (ISO/IEC-6429). (Lack of such support is extremely rare, and such
	# a case would tend to support setf rather than setaf.)
	color_prompt=yes
    else
	color_prompt=
    fi
fi

if [ "$color_prompt" = yes ]; then
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

# Git goodness:
# http://www.metaltoad.com/blog/git-drupal-primer
# GIT_PS1_SHOWDIRTYSTATE=true
# export PS1='[\u@mb \w$(__git_ps1)]\$ '
GIT_PS1_SHOWDIRTYSTATE=true
if [ "$color_prompt" = yes ]; then
PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]$(__git_ps1)\$ '
else
PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w$(__git_ps1)\$ '
fi
unset color_prompt force_color_prompt


# If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    ;;
*)
    ;;
esac

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# some more ls aliases
alias lt='ls -lArt'
alias ll='ls -AlF'
alias la='ls -A'
alias l='ls -CF'
alias ge=gedit
alias diceware=~/bin/diceware.sh
alias gs='git status'
alias cl='clear'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.

if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi

# Aliases
alias tun='pkill -f gargravarr-tunnels; ssh -fN -L 6667:localhost:6667 gargravarr -i /home/mike/.ssh/2011_michael_id_rsa -o ControlMaster=no gargravarr-tunnels'
alias o='gnome-open'
alias cvs_stat='cvs stat | grep File | grep -v Up-to-date'

# For drush make, export http_proxy for use with squid.
#export http_proxy=http://localhost:3128
export ftp_proxy=http://localhost:3128

# Set vim to default terminal editor
export EDITOR=vim

# CodeSniffer alias for Drupal_cs.
alias sniff='phpcs --standard=Drupal --extensions=php,module,inc,install,test,profile,theme,css'

# Output MOTD
#cat /etc/motd

# Showoff command autocomplete  https://github.com/ramnathv/slidifyLibraries/tree/master/inst/libraries/frameworks/showoff#bash-completion
#complete -F get_showoff_commands
#function get_showoff_commands()
#{
#  if [ -z $2 ] ; then
#    COMPREPLY=(`showoff help -c`)
#  else
#    COMPREPLY=(`showoff help -c $2`)
#  fi
#}

# Import drush example goodies
#if [ -f ~/.composer/vendor/drush/drush/examples/example.bashrc ]; then
#  . ~/.composer/vendor/drush/drush/examples/example.bashrc
#fi

#export PERL_LOCAL_LIB_ROOT="/home/michael/perl5";
#export PERL_MB_OPT="--install_base /home/michael/perl5";
#export PERL_MM_OPT="INSTALL_BASE=/home/michael/perl5";
#export PERL5LIB="/home/michael/perl5/lib/perl5/x86_64-linux-gnu-thread-multi:/home/michael/perl5/lib/perl5";
#export GEM_PATH="/usr/lib/ruby1.9.1/gems/1.9.1/"
#export GEM_PATH="/var/lib/gems/1.9.1/gems"
#export PATH="/home/michael/perl5/bin:/var/lib/gems/1.9.1/bin:$PATH";
export PATH=$HOME/.composer/vendor/bin:$PATH

. ~/bash_prompt.sh
#. ~/funzies.sh
if [ -f ~/.git-completion.bash ]; then
  . ~/.git-completion.bash
fi
