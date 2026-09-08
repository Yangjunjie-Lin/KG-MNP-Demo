// Actual product component with explicit synthetic props; no business API mock.
import {createRoot} from 'react-dom/client';
import {CandidateExplorer} from '../src/candidate-explorer';
import '../src/styles.css';

const labels=['DATA_PROPERTY','Entity','FIELD_TO_DATA_PROPERTY','INDIVIDUAL','DATA_PROPERTY_ASSERTION','CLASS_ASSERTION'];
const candidates=labels.map((label,index)=>({candidate_id:`synthetic-${index}`,candidate_kind:'ABOX',body:{candidate_type:label},evidence_refs:[],dependency_candidate_refs:index>3?['synthetic-3']:[]}));
createRoot(document.getElementById('root')!).render(<main className="projects"><h1>候选图展开回归</h1><CandidateExplorer candidates={candidates} edit={()=>{throw new Error('This read-only layout fixture never edits candidates');}}/></main>);
