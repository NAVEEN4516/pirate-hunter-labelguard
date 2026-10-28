/** Local PPTX export of the same content authored in the live Artifact session.
 * Usage: bundled-node export_presentation.mjs PROJECT_ROOT SKILL_DIR RUNTIME_PYTHON
 * Requires @oai/artifact-tool from the supplied workspace runtime.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
import { buildReport } from './build_presentation.mjs';

const [root,skillDir,runtimePython] = process.argv.slice(2);
if(!root || !skillDir || !runtimePython) throw new Error('Provide project root, skill directory and Python runtime');
const staging=path.join(root,'tmp/presentation');
const finalPath=path.join(root,'output/presentation/Pirate_Hunter_Project_Report.pptx');
await fs.mkdir(staging,{recursive:true});
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
await buildReport(presentation,root);
for(let i=0;i<presentation.slides.items.length;i++){
  const png=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(staging,`final-slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidatePath=path.join(staging,'candidate.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const {finalizePresentation}=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
  workspaceDir:root,candidatePath,finalPath,
  explicitTotalSlideCount:17,
  requiredNativeTableOwnerSlides:[2,5,6,7,10,11,12,14,15],
  requiredNativeChartOwnerSlides:[],
  pythonExecutable:runtimePython,
  integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',
    ...[2,5,6,7,10,11,12,14,15].flatMap(n=>['--require-native-table-slide',String(n)])],
  fontPolicy:{basis:'design',families:['Arial']},
  verifyArtifactToolImport:true,
  receiptPath:path.join(staging,'validation.json')
});
console.log(JSON.stringify(result,null,2));
