<?php
/*
$aliases['wef'] = array(
  'uri' => 'default',
  'root' => '/home/jhedstrom/work/clients/acquia-wef/docroot',
);

$aliases['dr'] = array(
  'uri' => 'dr.dev',
  'root' => '/home/jhedstrom/work/drupal',
);

$aliases['osu'] = array(
  'uri' => 'default',
  'root' => '/home/jhedstrom/work/clients/oregon_state_university/app/drupal',
);

$aliases['fc'] = array(
  'uri' => 'default',
  'root' => '/home/jhedstrom/work/clients/fluke/app/drupal',
);

$aliases['do'] = array(
  'uri' => 'do.dev',
  'root' => '/home/jhedstrom/work/drupal-6',
);

// Gargravarr aliases.
require '/home/jhedstrom/work/opensourcery/drush.gargravarr/aliases.drushrc.php';
*/
$aliases['wd-prod'] = array(
  'uri' => 'wisedecider.net',
  'user' => 'wisedeci',
  'root' => '/home/wisedeci/public_html'
);
$aliases['tscf-oa-prod'] = array(
  'uri' => 'tscfdirectorscorner.com',
  'user' => 'tscfdire',
  'root' => '/home/tscfdire/public_html'
);


// Gargravarr test hosts.
$gargravarr = array(
  'atka',
  'bachelor',
  'copahue',
  'demo',
  'dempo',
  'dempo',
  'eldfell',
  'fuego',
  'galeras',
  'hood',
  'isspah',
  'jornada',
  'karthala',
  'langila',
  'myoko',
  'nazko',
  'okataina',
  'pinatubo',
  'qualibou',
  'rainier',
  'shasta',
  'tsurumi',
  'undara',
  'visoke',
  'waiowa',
  'yellowstone',
  'zimina',
);
foreach ($gargravarr as $g_host) {
  $aliases[$g_host] = array(
    'uri' => 'default',
    'root' => '/var/www/' . $g_host . '/current',
    'remote-user' => $_SERVER['USER'],
    'remote-host' => 'gargravarr.opensourcery.com',
  );
}

$aliases['dempo-catalog'] = array(
  'uri' => 'default',
  'root' => '/var/www/dempo/current/catalog',
  'remote-user' => $_SERVER['USER'],
  'remote-host' => 'gargravarr.opensourcery.com',
);

