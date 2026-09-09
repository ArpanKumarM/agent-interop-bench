# Phase 9 F3 resolution study -- attempt-002 frozen analysis

- scientific freeze `32a76bf` / execution freeze `a347a8b` / attempt-002 freeze `e8fd793`
- analysis implementation SHA-256 `5c8301018886234c7721600f1678c0e218a76a02073e3b4b9fe47138faa2049f` (matches the frozen pin)
- band [0.25, 0.7] ; R=3 ; 1,536 completed trials ; 0 protocol errors

## CONFIRMATORY -- Q1 (fixed-domain theta_m, method S1f)

| model | theta_hat | 95% CI | half-width | classification |
|---|---|---|---|---|
| `gpt-5.6-sol` | 1.0000 | [1.0000, 1.0000] | 0.0000 | **ABOVE** |
| `gpt-5.6-terra` | 0.8229 | [0.7586, 0.8872] | 0.0643 | **ABOVE** |
| `gpt-5.6-luna` | 1.0000 | [1.0000, 1.0000] | 0.0000 | **ABOVE** |
| `claude-sonnet-5` | 0.8438 | [0.7616, 0.9259] | 0.0821 | **ABOVE** |

**Panel Q1 verdict: `FAILS`**

## CONFIRMATORY -- Q2 (paired P - N absolute risk difference Delta_m, uniform S1f)

| model | Delta_hat | 95% CI | half-width | detected (CI excludes 0) | Holm-adj p |
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
