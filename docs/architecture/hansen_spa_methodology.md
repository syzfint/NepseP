# Hansen Superior Predictive Ability (SPA) Methodology
**Author:** ApexMarketEngine Research
**Date:** 2026-10-22

## Studentized Loss Differential
Let $d_{k,t} = L_{0,t} - L_{k,t}$ denote the loss differential between benchmark model $0$ and alternative model $k$.
Hansen's SPA re-centers the test statistic:
$$\bar{d}_k^c = \bar{d}_k \mathbf{1}_{\{\bar{d}_k \ge -\sqrt{(2\log \log T) / T} \hat{\sigma}_k\}}$$
