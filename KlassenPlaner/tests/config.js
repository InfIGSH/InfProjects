/* Gemeinsame Pfade und Browser-Start für die Testskripte.
   Browser: nutzt PW_CHROME, falls gesetzt, sonst das von Playwright
   installierte Chromium. */
const path=require('path');
module.exports={
  TOOL:   'file://'+path.join(__dirname,'..','Klassenbildungstool_v1.html'),
  FIXTURES: path.join(__dirname,'fixtures')+path.sep,
  launchOpts(){
    return process.env.PW_CHROME ? {executablePath:process.env.PW_CHROME} : {};
  }
};
