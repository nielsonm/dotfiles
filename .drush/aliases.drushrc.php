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
$aliases['tek'] = array(
  'uri' => 'tek.com',
  'root' => '/home/michael/work/client/tek/app/pressflow/sites/tek.com',
  'user' => 'admin'
);
$aliases['psu.staging'] = array(
  'root' => '/var/www/current',
  'uri' => 'http://cota-staging.opensourcery.com',
  'remote-user' => 'jhedstrom',
  'remote-host' => 'cota-staging.opensourcery.com',
  'ssh-options' => '-p 2276',
);


// Gargravarr test hosts.
$gargravarr = array(
  'adams',
  'atka',
  'bachelor',
  'belknap',
  'capulin',
  'copahue',
  'cota-staging',
  'demo',
  'dempo',
  'dotsero',
  'ekarma',
  'eldfell',
  'fuego',
  'galeras',
  'gamalama',
  'hood',
  'isspah',
  'izalco',
  'jornada',
  'karthala',
  'langila',
  'lopevi',
  'myoko',
  'nazko',
  'newberry',
  'okataina',
  'opala',
  'pinatubo',
  'qualibou',
  'rainier',
  'regionalprograms',
  'shasta',
  'sotara',
  'trocon',
  'tsurumi',
  'undara',
  'visoke',
  'waiowa',
  'wurlali',
  'yellowstone',
  'zimina',
);
foreach ($gargravarr as $g_host) {
  $aliases[$g_host] = array(
    'uri' => 'default',
    'root' => '/var/www/' . $g_host . '/current',
    'remote-host' => 'gargravarr',
  );
}

$aliases['ilfi.test'] = array(
  'root' => '.',
  'uri' => 'test.living-future.org',
  'db-url' => 'mysql://pantheon:ede7c35763be4b77a718f1cae4def114@dbserver.test.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in:10821/pantheon',
  'db-allows-remote' => TRUE,
  'remote-host' => 'appserver.test.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in',
  'remote-user' => 'test.a6298332-55bd-4ad2-a984-782f0ab3cfdc',
  'ssh-options' => '-p 2222 -o "AddressFamily inet"',
  'path-aliases' => array(
    '%files' => 'code/sites/default/files'
  ),
);
$aliases['ilfi.live'] = array(
  'root' => '.',
  'uri' => 'www.living-future.org',
  'db-url' => 'mysql://pantheon:1c2fadf24ac94f848bcf4b477da80c5c@dbserver.live.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in:10046/pantheon',
  'db-allows-remote' => TRUE,
  'remote-host' => 'appserver.live.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in',
  'remote-user' => 'live.a6298332-55bd-4ad2-a984-782f0ab3cfdc',
  'ssh-options' => '-p 2222 -o "AddressFamily inet"',
  'path-aliases' => array(
    '%files' => 'code/sites/default/files'
  ),
);
$aliases['ilfi.dev'] = array(
  'root' => '.',
  'uri' => 'dev.ilfi.gotpantheon.com',
  'db-url' => 'mysql://pantheon:bf74f9353f7d400dab79722c86f91427@dbserver.dev.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in:11637/pantheon',
  'db-allows-remote' => TRUE,
  'remote-host' => 'appserver.dev.a6298332-55bd-4ad2-a984-782f0ab3cfdc.drush.in',
  'remote-user' => 'dev.a6298332-55bd-4ad2-a984-782f0ab3cfdc',
  'ssh-options' => '-p 2222 -o "AddressFamily inet"',
  'path-aliases' => array(
    '%files' => 'code/sites/default/files'
  ),
);

$directories = glob('/var/www/dev/*');

foreach ($directories as $directory) {
  $name = array_pop(explode('/', $directory));

  $aliases[$name] = array(
    'uri' => "http://$name.dev",
    'root' => $directory,
  );
}
