// Activity reflects received events. Animation indicates an active request;
// it never schedules stages, estimates progress, or generates status messages.
export const initialHRIDAYActivity = () => ({
  stage: 'connecting', text: 'Connecting to HRIDAY…', revision: 0,
  approachIds: [], reviewIds: [], stepIndex: 0, totalApproaches: null,
});
const stageOrder = { connecting: 0, understanding: 1, exploring: 2, retrieving: 2, calculating: 3, presenting: 3, working: 3, comparing: 4, reviewing: 4, composing: 5, writing: 6 };
const exploration = [
  'Exploring your question…',
  'Considering another approach…',
  'Looking at more possibilities…',
  'Considering another angle…',
  'Exploring one more approach…',
];

export function advanceHRIDAYActivity(previous, { type, data = {} }, tool = null) {
  let patch;
  if (type === 'war_room_init') {
    patch = { stage: 'understanding', text: 'Getting started on your question…', totalApproaches: data.delegates?.length || null };
  } else if (type === 'status') {
    if (data.phase === 1) {
      // Structured fields are preferred; the legacy stream includes [step/total].
      const legacy = /\[(\d+)\/(\d+)\]/.exec(data.message || '');
      const index = Number(data.step_index ?? legacy?.[1]);
      const total = Number(data.step_count ?? legacy?.[2]);
      if (Number.isSafeInteger(index) && index > 0 && index <= total) {
        if (index <= previous.stepIndex) return previous;
        patch = { stage: 'exploring', text: exploration[Math.min(index - 1, exploration.length - 1)], stepIndex: index, totalApproaches: total };
      } else patch = { stage: 'exploring', text: 'Exploring your question…' };
    } else if (data.phase === 2) patch = { stage: 'comparing', text: 'Comparing possible answers…' };
    else if (data.phase === 3) patch = { stage: 'composing', text: 'Bringing your answer together…' };
    else if (data.phase === 'planning') patch = { stage: 'understanding', text: 'Reviewing your question…' };
    else if (data.phase === 'retrieval') patch = { stage: 'retrieving', text: 'Finding relevant information…' };
    else if (data.phase === 'generating') patch = { stage: 'composing', text: 'Putting your response into words…' };
    else if (data.phase === 'tool') {
      patch = tool?.name === 'presentation'
        ? { stage: 'presenting', text: 'Building your presentation…' }
        : ['arithmetic', 'calculate', 'industrial_metric', 'analytical_plan'].includes(tool?.name)
          ? { stage: 'calculating', text: 'Working through the calculation…' }
          : { stage: 'working', text: 'Working on your request…' };
    } else if (data.step === 'ready') patch = { stage: 'composing', text: 'The relevant findings are ready…' };
  } else if (type === 'candidate_answer' || type === 'delegate_perspective') {
    if (!data.delegate_id || previous.approachIds.includes(data.delegate_id)
      || !(data.candidate_answer || data.perspective)) return previous;
    const approachIds = [...previous.approachIds, data.delegate_id];
    patch = { stage: 'exploring', approachIds,
      text: approachIds.length === previous.totalApproaches ? 'The possible responses are ready…'
        : approachIds.length === 1 ? 'An initial response is ready…' : 'Another approach is ready…' };
  } else if (type === 'delegate_vote') {
    if (!data.delegate_id || previous.reviewIds.includes(data.delegate_id)) return previous;
    const reviewIds = [...previous.reviewIds, data.delegate_id];
    patch = { stage: 'reviewing', reviewIds,
      text: reviewIds.length === previous.totalApproaches ? 'The reviews are complete…'
        : reviewIds.length === 1 ? 'A review is complete…' : 'Another review is complete…' };
  } else if (type === 'token' && data.token) {
    patch = { stage: 'writing', text: 'Writing your answer…' };
  }
  // Unknown events and late earlier-phase messages cannot invent or rewind activity.
  if (!patch || stageOrder[patch.stage] < stageOrder[previous.stage]) return previous;
  if (Object.entries(patch).every(([key, value]) => previous[key] === value)) return previous;
  return { ...previous, ...patch, revision: previous.revision + 1 };
}
