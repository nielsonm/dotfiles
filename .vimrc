set autoindent
set expandtab
set incsearch
set mouse=a
set shiftwidth=2
set showcmd
set smartindent
set tabstop=2
colorscheme desert
syntax on

"setlocal spell spelllang=en_us"

filetype plugin indent on

let php_sql_query = 1
let php_parent_error_close = 1
" let php_folding = 1

if has("autocmd")
  " Drupal's PHP file extensions
  augroup module
    autocmd BufRead,BufNewFile *.engine set filetype=php
    autocmd BufRead,BufNewFile *.inc set filetype=php
    autocmd BufRead,BufNewFile *.install set filetype=php
    autocmd BufRead,BufNewFile *.module set filetype=php
    autocmd BufRead,BufNewFile *.profile set filetype=php
    autocmd BufRead,BufNewFile *.test set filetype=php
    autocmd BufRead,BufNewFile *.theme set filetype=php
    autocmd BufRead,BufNewFile *.view set filetype=php
  augroup END
  augroup lesscss
    autocmd BufRead,BufNewFile *.less set filetype=less
  augroup END
  augroup info
    autocmd BufRead,BufNewFile *.info set filetype=drupal-info
    autocmd BufRead,BufNewFile *.make set filetype=drupal-info
  augroup END
endif

" Highlight redundant whitespaces and tabs.
highlight RedundantSpaces ctermbg=red guibg=orange
match RedundantSpaces /\s\+$\| \+\ze\t\|\t/

" Highlight chars that go over the 80-column limit
"highlight OverLength ctermbg=red ctermfg=white guibg=red guifg=white
"match OverLength '\%81v.*'


let g:syntastic_phpcs_conf=" --standard=Drupal --extensions=php,module,inc,install,test,profile,theme"

" from https://github.com/spf13/spf13-vim/blob/master/.vimrc
  if has('statusline')
    set laststatus=2
    " Broken down into easily includeable segments
    set statusline=%<%f\    " Filename
    set statusline+=%w%h%m%r " Options
    " set statusline+=%{fugitive#statusline()} "  Git Hotness
    set statusline+=\ [%{&ff}/%Y]            " filetype
    set statusline+=\ [%{getcwd()}]          " current dir
    set statusline+=%#warningmsg#
    set statusline+=%{SyntasticStatuslineFlag()}
    set statusline+=%*
    let g:syntastic_enable_signs=1
    set statusline+=%=%-14.(%l,%c%V%)\ %p%%  " Right aligned file nav info
  endif
