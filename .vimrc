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

"setlocal spell spelllang=en_us
autocmd BufRead,BufNewFile *.md setlocal spell
imap <F9> <C-o>:setlocal spell! spelllang=en_us<CR>

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

" Behat feature https://github.com/veloce/vim-behat
let feature_filetype='behat'

" Cucumber syntax
au Bufread,BufNewFile *.feature set filetype=gherkin
au! Syntax gherkin source ~/.vim/cucumber.vim

" Highlight redundant whitespaces and tabs.
highlight RedundantSpaces ctermbg=red guibg=orange
match RedundantSpaces /\s\+$\| \+\ze\t\|\t/

" Pathogen goodness
execute pathogen#infect()

" Cucumber auto alignment
inoremap <silent> <Bar>   <Bar><Esc>:call <SID>align()<CR>a

function! s:align()
  let p = '^\s*|\s.*\s|\s*$'
  if exists(':Tabularize') && getline('.') =~# '^\s*|' && (getline(line('.')-1) =~# p || getline(line('.')+1) =~# p)
    let column = strlen(substitute(getline('.')[0:col('.')],'[^|]','','g'))
    let position = strlen(matchstr(getline('.')[0:col('.')],'.*|\s*\zs.*'))
    Tabularize/|/l1
    normal! 0
    call search(repeat('[^|]*|',column).'\s\{-\}'.repeat('.',position),'ce',line('.'))
  endif
endfunction

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
  set statusline+=%{fugitive#statusline()} "  Git Hotness
  set statusline+=\ [%{&ff}/%Y]            " filetype
  set statusline+=\ [%{getcwd()}]          " current dir
  set statusline+=%#warningmsg#
  set statusline+=%{SyntasticStatuslineFlag()}
  set statusline+=%*
  let g:syntastic_enable_signs=1
  set statusline+=%=%-14.(%l,%c%V%)\ %p%%  " Right aligned file nav info
endif
