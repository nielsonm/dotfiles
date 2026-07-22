# Entomological Society of America - ESA

[![Prod](https://img.shields.io/badge/Prod-www.entsoc.org-0A66C2)](https://www.entsoc.org)
[![Test](https://img.shields.io/badge/Test-esa--dpl.taoti.io-0A66C2)](https://esa-dpl.taoti.io)
[![AWS Deploy (Main/master)](https://github.com/Taoti/esasoc/actions/workflows/deploy_aws_drupal.yml/badge.svg)](https://github.com/Taoti/esasoc/actions/workflows/deploy_aws_drupal.yml)
[![AWS Promote (main/master)](https://github.com/Taoti/esasoc/actions/workflows/promote_aws_drupal.yml/badge.svg)](https://github.com/Taoti/esasoc/actions/workflows/promote_aws_drupal.yml)

This is a Composer-managed Drupal website project repository for the Entomological Society of America (ESA).

## Custom Modules Executive Summary

The `web/modules/custom` directory contains custom Drupal modules designed to extend the Entomological Society of America web portal with Single Sign-On (SSO) authentication, domain path integrations, block level access permissions, Drupal 7 content migration tools, and enterprise SAML authentication integration.

### 1. ESA SSO (`esa_sso`)
The ESA SSO module handles user authentication for the ESA web portal. It authenticates users against the central ESA identity provider and seamlessly manages login/logout flows and user session synchronization for portal access.

### 2. ESA Miscellaneous (`esa_miscellaneous`)
The ESA Miscellaneous module aggregates site-specific utility features and customizations that extend core behavior without requiring standalone modules. It integrates domain path functionality (`domain_path`), implements form alters (`hook_form_alter`) for custom forms, defines site-wide cron routines (`hook_cron`), manages page asset attachments (`hook_page_attachments`), and provides a custom field formatter (`DateTimeSiteFormatter`).

### 3. ESA Block Permissions (`esa_block_permissions`)
Extending Drupal's block field system (`drupal:block_field`), this module implements granular view and access control permissions for individual block fields and instances across content entities.

### 4. ESA D7 Import (`esa_d7_import`)
A comprehensive migration feature module built on Drupal's Migrate API (`migrate`, `migrate_plus`). It defines migration YML configurations and custom migration process plugins to extract, transform, and import legacy content, nodes, taxonomy terms, and paragraphs from the previous Drupal 7 site into Drupal 10.

### 5. miniOrange SAML Service Provider Enterprise (`miniorange_saml`)
An enterprise-grade SAML 2.0 Service Provider module enabling single sign-on authentication between the ESA Drupal site and external SAML Identity Providers (IdP). It provides administrative management interfaces, attribute mapping, and secure assertion handling.

## Custom Modules Code Metrics & Inventory

| Module Name | PHP Files / Lines | JS Files / Lines | CSS Files / Lines | YML Files | Key Components |
|---|---|---|---|---|---|
| **esa_sso** | 17 / 2152 lines | 0 / 0 lines | 0 / 0 lines | 3 | Hooks: hook_form_alter |
| **esa_miscellaneous** | 7 / 622 lines | 1 / 13 lines | 0 / 0 lines | 3 | Hooks: hook_cron, hook_page_attachments, hook_form_alter; Plugins: DateTimeSiteFormatter (FieldFormatter) |
| **esa_block_permissions** | 2 / 90 lines | 0 / 0 lines | 0 / 0 lines | 2 | Config and Metadata |
| **esa_d7_import** | 7 / 391 lines | 0 / 0 lines | 0 / 0 lines | 34 | Config and Metadata |
| **miniorange_saml** | 42 / 12060 lines | 10 / 246 lines | 3 / 976 lines | 13 | Hooks: hook_cron, hook_form_alter, hook_theme |

## Technical Notes & Getting Started

### Local Development Environment
The project runs locally using Lando:
- Start the environment: `lando start`
- Stop the environment: `lando stop`
- Run composer inside container: `lando composer <command>`
- Run drush: `lando drush <command>`
