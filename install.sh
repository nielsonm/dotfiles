#!/bin/bash
# Installation script to copy config into my home directory.


# Config step - Let's get settings up & running.
echo -e "Copy config to homedir.  (default /Users/mnielson/)"
DefaultDestDir='/Users/mnielson/'
SrcDir=`pwd`

read NewDestDir
if [[ -z $NewDestDir ]]; then
    DestDir=$DefaultDestDir
else
    DestDir=$NewDestDir
fi
echo -e "Copying config to $DestDir."


cd ${DestDir}

FilesToCopy=(".bash_profile" ".bashrc" ".git-completion.bash" ".vimrc" "bash_prompt.sh" "funzies.sh" "print_colors.sh")

DirectoriesToCopy=(".drush" ".vim")


# Loop through the files and install them.
for file in ${FilesToCopy[@]}; do
   # Check for the file to exist before copying the file into the homedir.
   if [ ! -f $file ]; then
       echo "File $file not found!"
       cp -piv ${SrcDir}/${file} ${file}
   fi
done

# TODO Copy over the directories.


# Infect vim with pathogen.
mkdir -p ~/.vim/autoload ~/.vim/bundle && \
curl -LSso ~/.vim/autoload/pathogen.vim https://tpo.pe/pathogen.vim


mkdir -p ~/.vim/pack/tpope/start
cd ~/.vim/pack/tpope/start
git clone https://tpope.io/vim/fugitive.git
vim -u NONE -c "helptags fugitive/doc" -c q

cd ~/.vim/bundle && \
git clone --depth=1 https://github.com/vim-syntastic/syntastic.git



# Unwrap the gitconfig and copy it over.

cp -piv ${SrcDir}/.gitconfig.safe .gitconfig

# Install homebrew
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
