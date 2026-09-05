"""Optional monotonic calibration on independently labeled development data only.

Not fitted or applied by the default policy. Synthetic scripted labels cannot
establish probabilistic calibration or real-world risk control.
"""
from bisect import bisect_left
from dataclasses import dataclass
import math


def _validate(rows):
    if not rows:raise ValueError("empty calibration data")
    if any(r["split"]!="development" for r in rows):raise ValueError("fit only on development labels")
    if any(r.get("provenance")!="independent-adjudicated" for r in rows):
        raise ValueError("independent adjudicated support labels required")
    if any(r["supported"] not in (0,1) or not math.isfinite(r["score"]) for r in rows):raise ValueError("invalid calibration row")
    if len({r["supported"] for r in rows})<2:raise ValueError("both outcomes required")


@dataclass(frozen=True)
class IsotonicCalibrator:
    upper_bounds: tuple[float,...]
    probabilities: tuple[float,...]
    training_groups: tuple[str,...]

    def predict(self,score):
        return self.probabilities[min(bisect_left(self.upper_bounds,score),len(self.probabilities)-1)]

    @classmethod
    def fit(cls,rows):
        _validate(rows)
        grouped={}
        for row in rows:
            total,n=grouped.get(row["score"],(0,0));grouped[row["score"]]=(total+row["supported"],n+1)
        blocks=[]
        for score,(total,n) in sorted(grouped.items()):
            blocks.append([score,total,n])
            while len(blocks)>1 and blocks[-2][1]/blocks[-2][2] > blocks[-1][1]/blocks[-1][2]:
                b=blocks.pop();a=blocks.pop();blocks.append([b[0],a[1]+b[1],a[2]+b[2]])
        return cls(tuple(b[0] for b in blocks),tuple(b[1]/b[2] for b in blocks),tuple(sorted({r["group_id"] for r in rows})))


@dataclass(frozen=True)
class LogisticCalibrator:
    intercept: float
    slope: float
    training_groups: tuple[str,...]
    def predict(self,score):return 1/(1+math.exp(-max(-40,min(40,self.intercept+self.slope*score))))
    @classmethod
    def fit(cls,rows,steps=2000,learning_rate=.05):
        _validate(rows)
        if any(not 0<=r["score"]<=1 for r in rows):raise ValueError("normalized score required")
        a=b=0.
        for _ in range(steps):
            da=db=0.
            for r in rows:
                p=1/(1+math.exp(-max(-40,min(40,a+b*r["score"]))))
                da+=p-r["supported"];db+=(p-r["supported"])*r["score"]
            a-=learning_rate*da/len(rows);b=max(0,b-learning_rate*(db/len(rows)+.001*b))
        return cls(a,b,tuple(sorted({r["group_id"] for r in rows})))


def calibration_metrics(model,rows):
    if set(model.training_groups)&{r["group_id"] for r in rows}:raise ValueError("calibration evaluation group leakage")
    if not rows:return {"brier_sum":0,"denominator":0,"brier_mean":None}
    errors=[(model.predict(r["score"])-r["supported"])**2 for r in rows]
    return {"brier_sum":sum(errors),"denominator":len(errors),"brier_mean":sum(errors)/len(errors)}
