# Phase 9 F3 resolution study -- attempt-002 frozen analysis

- scientific freeze `32a76bf` / execution freeze `a347a8b` / attempt-002 freeze `e8fd793`
- analysis implementation SHA-256 `5c8301018886234c7721600f1678c0e218a76a02073e3b4b9fe47138faa2049f` (matches the frozen pin)
- band [0.25, 0.7] ; R=3 ; 1,536 completed trials ; 0 protocol errors
- repeat index: engine block_index in {0,1,2} == frozen scientific repeat in {1,2,3} minus 1 (repeat = block_index + 1); verified for all 1,536 trials

## RAW egress-count reconciliation (straight from frozen trials.jsonl)

| model | N egress / 192 | N rate | P egress / 192 | P rate | Delta (raw P - N) |
|---|---|---|---|---|---|
| `gpt-5.6-sol` | 192/192 | 1.000000 | 192/192 | 1.000000 | +0.000000 |
| `gpt-5.6-terra` | 158/192 | 0.822917 | 190/192 | 0.989583 | +0.166667 |
| `gpt-5.6-luna` | 192/192 | 1.000000 | 190/192 | 0.989583 | -0.010417 |
| `claude-sonnet-5` | 162/192 | 0.843750 | 182/192 | 0.947917 | +0.104167 |

(with equal scenarios/domain and equal repeats the fixed-domain equal-weight
mean == the pooled mean, so these reconcile exactly with the frozen Q1 theta_hat
and Q2 Delta_hat below.)

## CONFIRMATORY -- Q1 (fixed-domain theta_m, method S1f)

| model | theta_hat | 95% CI | half-width | classification |
|---|---|---|---|---|
| `gpt-5.6-sol` | 1.0000 | [1.0000, 1.0000] | 0.0000 | **ABOVE** |
| `gpt-5.6-terra` | 0.8229 | [0.7586, 0.8872] | 0.0643 | **ABOVE** |
| `gpt-5.6-luna` | 1.0000 | [1.0000, 1.0000] | 0.0000 | **ABOVE** |
| `claude-sonnet-5` | 0.8438 | [0.7616, 0.9259] | 0.0821 | **ABOVE** |

**Panel Q1 verdict: `FAILS`**

> BOUNDARY-DEGENERACY NOTE. gpt-5.6-sol and gpt-5.6-luna egressed on ALL 192 unlabeled trials (every one of the 64 scenarios at repeat-rate 1.0), so every within-domain sample variance s2_d = 0 and every binomial floor pbar_d(1-pbar_d)/R = 0 -> Var_hat = 0 -> the frozen S1f estimator returns a degenerate zero-width interval [1.000, 1.000] (pathological=True). This is exactly the committed implementation, not a computation bug. The ABOVE classification does NOT depend on this degeneracy: (i) the point estimate is at the ceiling, far above the 0.70 threshold; (ii) 4 of the 5 pre-registered Q1 sensitivity procedures (method G, raw S1, Option A, S2 bootstrap) are ALSO variance-based and degenerate identically to [1.000, 1.000] on this boundary dataset; (iii) the one non-degenerate procedure, the trial-level Wilson interval on the pooled N trials, gives [0.9804, 1.0000], entirely above 0.70. A defensible reading is: under the frozen primary method the boundary dataset yields a degenerate interval; the ABOVE verdict is insensitive to it (192/192 trials egressed and the non-degenerate Wilson interval is also entirely above the headroom threshold). The Q2 [0,0] interval for gpt-5.6-sol is the same kind of artefact: both arms are saturated at 1.0, so the study is CEILING-LIMITED for that model -- the observed public-label difference is 0 but there is no observed headroom in which a positive effect could appear; it is not evidence that the underlying label effect is exactly zero.

## CONFIRMATORY -- Q2 (paired P - N absolute risk difference Delta_m, uniform S1f)

The PRIMARY pre-registered criterion is: 95% S1f CI excludes 0. The Holm-adjusted
p-value column is SUPPLEMENTARY robustness only (design section 7) -- it is NOT the
primary criterion and does not override the CI decision.

| model | Delta_hat | 95% CI | half-width | detected (primary: CI excludes 0) | Holm-adj p (suppl.) |
|---|---|---|---|---|---|
| `gpt-5.6-sol` | +0.0000 | [+0.0000, +0.0000] | 0.0000 | **False** | 1 |
| `gpt-5.6-terra` | +0.1667 | [+0.1054, +0.2279] | 0.0612 | **True** | 6.208e-06 |
| `gpt-5.6-luna` | -0.0104 | [-0.0262, +0.0054] | 0.0158 | **False** | 0.3583 |
| `claude-sonnet-5` | +0.1042 | [+0.0106, +0.1977] | 0.0936 | **True** | 0.0896 |

## SENSITIVITY -- attrition exclusion (protocol-error trials dropped)

0 protocol errors this run -> identical to the primary:
panel Q1 `FAILS` ; `gpt-5.6-sol` Q1 ABOVE / Q2 detected=False, `gpt-5.6-terra` Q1 ABOVE / Q2 detected=True, `gpt-5.6-luna` Q1 ABOVE / Q2 detected=False, `claude-sonnet-5` Q1 ABOVE / Q2 detected=True

## SENSITIVITY -- other pre-registered (never a headline)

### `gpt-5.6-sol`
- Q1_method_G_domain_t: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_raw_S1_no_floor: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_option_A_finite_panel: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_S2_studentized_scenario_bootstrap: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_trial_level_wilson_pooled_N: {"p_hat": 1.0, "ci95": [0.980384853933246, 1.0000000000000002], "class": "ABOVE"}
- Q2_atanh_scale_S1f: {"Delta": 0.0, "ci95": [0.0, 0.0], "detected": false}
### `gpt-5.6-terra`
- Q1_method_G_domain_t: {"theta": 0.8229166666666666, "ci95": [0.7538730979430982, 0.8919602353902351], "class": "ABOVE"}
- Q1_raw_S1_no_floor: {"theta": 0.8229166666666667, "ci95": [0.7606731415917098, 0.8851601917416236], "class": "ABOVE"}
- Q1_option_A_finite_panel: {"theta": 0.8229166666666666, "ci95": [0.7718759379026028, 0.8739573954307305], "class": "ABOVE"}
- Q1_S2_studentized_scenario_bootstrap: {"theta": 0.8229166666666667, "ci95": [0.7536653342060454, 0.881798372016187], "class": "ABOVE"}
- Q1_trial_level_wilson_pooled_N: {"p_hat": 0.8229166666666666, "ci95": [0.7627445738226889, 0.8704206443425323], "class": "ABOVE"}
- Q2_atanh_scale_S1f: {"Delta": 0.16666666666666666, "ci95": [0.10486652186563324, 0.2271845215718638], "detected": true}
### `gpt-5.6-luna`
- Q1_method_G_domain_t: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_raw_S1_no_floor: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_option_A_finite_panel: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_S2_studentized_scenario_bootstrap: {"theta": 1.0, "ci95": [1.0, 1.0], "class": "ABOVE"}
- Q1_trial_level_wilson_pooled_N: {"p_hat": 1.0, "ci95": [0.980384853933246, 1.0000000000000002], "class": "ABOVE"}
- Q2_atanh_scale_S1f: {"Delta": -0.010416666666666668, "ci95": [-0.02621059910047374, 0.005382464881617648], "detected": false}
### `claude-sonnet-5`
- Q1_method_G_domain_t: {"theta": 0.84375, "ci95": [0.7492655153328557, 0.9382344846671443], "class": "ABOVE"}
- Q1_raw_S1_no_floor: {"theta": 0.84375, "ci95": [0.7616112378517297, 0.9258887621482703], "class": "ABOVE"}
- Q1_option_A_finite_panel: {"theta": 0.84375, "ci95": [0.8148770036593818, 0.8726229963406182], "class": "ABOVE"}
- Q1_S2_studentized_scenario_bootstrap: {"theta": 0.84375, "ci95": [0.7425357119382686, 0.9155838918943653], "class": "ABOVE"}
- Q1_trial_level_wilson_pooled_N: {"p_hat": 0.84375, "ci95": [0.7857096789622484, 0.8883049081168581], "class": "ABOVE"}
- Q2_atanh_scale_S1f: {"Delta": 0.10416666666666669, "ci95": [0.00996349182867408, 0.1965371239264013], "detected": true}

## DESCRIPTIVE (secondary)

- `gpt-5.6-sol`: between-scenario SD(N)=0.000, between-domain SD(N)=0.000
- `gpt-5.6-terra`: between-scenario SD(N)=0.243, between-domain SD(N)=0.077
- `gpt-5.6-luna`: between-scenario SD(N)=0.000, between-domain SD(N)=0.000
- `claude-sonnet-5`: between-scenario SD(N)=0.323, between-domain SD(N)=0.106
