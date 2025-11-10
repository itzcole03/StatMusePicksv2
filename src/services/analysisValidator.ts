import { ParsedProjection } from '../types';

export function validateOutput(arr: any[], projections: ParsedProjection[], contextsMap: Record<string, any> | null) {
  const reasons: string[] = [];
  if (!Array.isArray(arr)) { reasons.push('Output is not a JSON array'); return { ok: false, reasons }; }
  if (arr.length !== projections.length) reasons.push(`Expected ${projections.length} elements, got ${arr.length}`);
  arr.forEach((it, idx) => {
    if (!it || typeof it !== 'object') { reasons.push(`Item ${idx} is not an object`); return; }
    const required = ['player','stat','line','recommendation','confidence','numericEvidence','reasoning','dataUsed'];
    for (const k of required) if (!(k in it)) reasons.push(`Item ${idx} missing key '${k}'`);
    if (it.recommendation !== null && it.recommendation !== 'OVER' && it.recommendation !== 'UNDER') reasons.push(`Item ${idx} recommendation must be OVER/UNDER/null`);
    if (it.confidence && !['High','Medium','Low'].includes(it.confidence)) reasons.push(`Item ${idx} confidence must be High/Medium/Low`);
    // numericEvidence check against contexts when available (tolerant)
    if (contextsMap) {
      const p = projections[idx];
      const ctx = contextsMap[p.id];
      const provided = it.numericEvidence || {};
      // recentGames: ensure provided values appear in trusted context (order-insensitive)
      if (provided.recentGames && ctx && Array.isArray(ctx.recentGames)) {
        const provVals = (provided.recentGames || []).map((a:any)=> a && a.statValue != null ? Number(a.statValue) : null).filter((v:any)=>v!=null);
        const ctxVals = (ctx.recentGames || []).map((b:any)=> b && b.statValue != null ? Number(b.statValue) : null).filter((v:any)=>v!=null);
        for (const v of provVals) {
          if (!ctxVals.includes(v)) { reasons.push(`Item ${idx} recentGames value ${v} not present in trusted context`); break; }
        }
      }
      // seasonAvg: allow small absolute or relative tolerance
      if (provided.seasonAvg != null && ctx && ctx.seasonAvg != null) {
        const aval = Number(provided.seasonAvg);
        const bval = Number(ctx.seasonAvg);
        const tol = Math.max(0.5, Math.abs(bval) * 0.05);
        if (isNaN(aval) || Math.abs(aval - bval) > tol) reasons.push(`Item ${idx} seasonAvg mismatch with trusted context beyond tolerance`);
      }
      // opponent validation: allow small tolerances and missing fields
      if (provided.opponent && ctx && ctx.opponent) {
        const pa = provided.opponent;
        const ca = ctx.opponent;
        if (pa.name && ca.name && pa.name !== ca.name) reasons.push(`Item ${idx} opponent.name mismatch (model vs trusted)`);
        if (pa.defensiveRating != null && ca.defensiveRating != null) {
          const pd = Number(pa.defensiveRating);
          const cd = Number(ca.defensiveRating);
          if (isNaN(pd) || Math.abs(pd - cd) > 1.0) reasons.push(`Item ${idx} opponent.defensiveRating mismatch beyond tolerance`);
        }
        if (pa.pace != null && ca.pace != null) {
          const pp = Number(pa.pace);
          const cp = Number(ca.pace);
          if (isNaN(pp) || Math.abs(pp - cp) > 1.0) reasons.push(`Item ${idx} opponent.pace mismatch beyond tolerance`);
        }
      }
      // projectedMinutes validation: allow ±1.5 minutes
      if (provided.projectedMinutes != null && ctx && ctx.projectedMinutes != null) {
        const pm = Number(provided.projectedMinutes);
        const cm = Number(ctx.projectedMinutes);
        if (isNaN(pm) || Math.abs(pm - cm) > 1.5) reasons.push(`Item ${idx} projectedMinutes mismatch beyond tolerance`);
      }
    }
  });
  return { ok: reasons.length === 0, reasons };
}
