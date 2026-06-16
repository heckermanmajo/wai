# wai

## Product-Value

## Folder
### /interface
### /scripts
### /modules
#### /modules/<agent>
#### /modules/<agent>/<tool>/

## databases
### Admin DB
Hier werden die Customers gepflegt -> unsere Customers; und ebenso unsere 
admin accounts. Zudem wird heir gefpegt welchen zugirff unsere kunden haben
usw. Also alles was nicht unsere kunden selbst eiunstellen können.

### Logging DB
hier landen events, die den kunden nicht interessieren, aber für uns als plattform
betreiber relevant sind um das ganze zu adminsitrieren und zu überwachen.

### Tenant DB 
Auf den Teannt dbs sind alle daten die dem kunden gehören.

## Agents vs Tools
Agents haben 'descision' capability
Tools nicht, selbst wenn sie AI calls machen
Agents dealen mit unsicherheit/ambiguität
Tools liefern eine klare aktionsoberfläche
Agents un tools sind im grunde MCP server mit APIS.

## Rollen & Rechnte-Management
### Plattform-Roles VS tenant-roles

## SQL-Creation
- agenten können sql abfragen erstellen und die an das db tool senden

## FORM/View-Creation

## Logging/Debug/Visibility
- jeder tenant-db hat einen support user, der dann mehr sehen kann, 
  also so details usw. also die debug info - dort wo der normale nutzer
  nur den default output sieht

## Learning der Agenten

## Hearthbeat

## Agenten-Magie
- die meiste Abläufe muss man nicht mehr "coden", sondern als
  MD file festhalten.