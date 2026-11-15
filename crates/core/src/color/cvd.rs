//! Symulacja daltonizmu (CVD) w liniowym sRGB: Brettel 1997, Viénot 1999, Machado 2009.
//!
//! Macierze i sposób stosowania nasilenia jak w coloraide (`filters/cvd.py`) i `fast.py`:
//! Viénot i Brettel mieszają liniowo kolor wyjściowy z pełną symulacją, Machado interpoluje
//! między macierzami dla nasilenia co 0,1. Wynik to OKLab bez przycinania do gamutu.

use crate::scalar::Scalar;

use super::convert::{dot3, linear_srgb_to_oklab, mat3, oklab_to_linear_srgb};
use super::{CvdKind, CvdMethod};

/// Symulacja widzenia koloru OKLab przy danym typie i metodzie; `severity` obcinane do [0, 1].
pub fn simulate_cvd<T: Scalar>(
    lab: [T; 3],
    kind: CvdKind,
    method: CvdMethod,
    severity: f64,
) -> [T; 3] {
    let severity = if severity.is_nan() { 0.0 } else { severity.clamp(0.0, 1.0) };
    let lin = oklab_to_linear_srgb(lab);
    let out = match method {
        CvdMethod::Vienot => {
            let full = mat3(vienot(kind), lin);
            lerp(lin, full, severity)
        }
        CvdMethod::Brettel => {
            let (w1, w2, sep) = brettel(kind);
            let lms = mat3(&CVD_LRGB_TO_LMS, lin);
            let wing = if dot3(sep, lms).val() > 0.0 { w2 } else { w1 };
            lerp(lin, mat3(wing, lms), severity)
        }
        CvdMethod::Machado => {
            let table = machado(kind);
            let s = severity * 10.0;
            let i = s as usize;
            let low = mat3(&table[i], lin);
            if (i as f64) != s && i < 10 {
                lerp(low, mat3(&table[i + 1], lin), s - i as f64)
            } else {
                low
            }
        }
    };
    linear_srgb_to_oklab(out)
}

/// `a + (b − a) · t`; dla `t ≥ 1` dokładnie `b`.
#[inline]
fn lerp<T: Scalar>(a: [T; 3], b: [T; 3], t: f64) -> [T; 3] {
    if t >= 1.0 {
        return b;
    }
    std::array::from_fn(|i| a[i] + (b[i] - a[i]).scale(t))
}

fn vienot(kind: CvdKind) -> &'static [[f64; 3]; 3] {
    match kind {
        CvdKind::Protan => &VIENOT_PROTAN,
        CvdKind::Deutan => &VIENOT_DEUTAN,
        CvdKind::Tritan => &VIENOT_TRITAN,
    }
}

type Wings = (&'static [[f64; 3]; 3], &'static [[f64; 3]; 3], &'static [f64; 3]);

/// Dwie półpłaszczyzny Brettela (macierze LMS → liniowy sRGB) i normalna płaszczyzny podziału.
fn brettel(kind: CvdKind) -> Wings {
    match kind {
        CvdKind::Protan => (&BRETTEL_PROTAN_W1, &BRETTEL_PROTAN_W2, &BRETTEL_PROTAN_SEP),
        CvdKind::Deutan => (&BRETTEL_DEUTAN_W1, &BRETTEL_DEUTAN_W2, &BRETTEL_DEUTAN_SEP),
        CvdKind::Tritan => (&BRETTEL_TRITAN_W1, &BRETTEL_TRITAN_W2, &BRETTEL_TRITAN_SEP),
    }
}

fn machado(kind: CvdKind) -> &'static [[[f64; 3]; 3]; 11] {
    match kind {
        CvdKind::Protan => &MACHADO_PROTAN,
        CvdKind::Deutan => &MACHADO_DEUTAN,
        CvdKind::Tritan => &MACHADO_TRITAN,
    }
}

// ---------------------------------------------------------------------------
// Stałe z coloraide `filters/cvd.py` (pełna precyzja)
// ---------------------------------------------------------------------------

const CVD_LRGB_TO_LMS: [[f64; 3]; 3] = [
    [0.178824041258, 0.4351609057000001, 0.04119349692],
    [0.034556423182, 0.27155382458, 0.038671308360000003],
    [0.000299565576, 0.0018430896, 0.01467086136],
];

const BRETTEL_PROTAN_W1: [[f64; 3]; 3] = [
    [0.0, 4.645203550257065, -35.779576941742434],
    [0.0, 3.1614562071112173, -5.353537465326408],
    [0.0, -0.49202224438116643, 69.56547088528569],
];

const BRETTEL_PROTAN_W2: [[f64; 3]; 3] = [
    [0.0, 4.500783062899838, -32.818059625581405],
    [0.0, 3.179741536008844, -5.728500319648271],
    [0.0, -0.4913704825845725, 69.55210571887513],
];

const BRETTEL_PROTAN_SEP: [f64; 3] = [0.0, 0.016813516536000002, -0.344781556122];

const VIENOT_PROTAN: [[f64; 3]; 3] = [
    [0.11238276122216405, 0.8876172387778362, 5.551115123125783e-17],
    [0.11238276122216398, 0.8876172387778362, -2.7755575615628914e-17],
    [0.0040057682730469425, -0.004005768273046939, 1.0],
];

const MACHADO_PROTAN: [[[f64; 3]; 3]; 11] = [
    [[1.0, 0.0, -0.0], [0.0, 1.0, 0.0], [-0.0, -0.0, 1.0]],
    [
        [0.856167, 0.182038, -0.038205],
        [0.029342, 0.955115, 0.015544],
        [-0.00288, -0.001563, 1.004443],
    ],
    [
        [0.734766, 0.334872, -0.069637],
        [0.05184, 0.919198, 0.028963],
        [-0.004928, -0.004209, 1.009137],
    ],
    [
        [0.630323, 0.465641, -0.095964],
        [0.069181, 0.890046, 0.040773],
        [-0.006308, -0.007724, 1.014032],
    ],
    [
        [0.539009, 0.579343, -0.118352],
        [0.082546, 0.866121, 0.051332],
        [-0.007136, -0.011959, 1.019095],
    ],
    [
        [0.458064, 0.679578, -0.137642],
        [0.092785, 0.846313, 0.060902],
        [-0.007494, -0.016807, 1.024301],
    ],
    [
        [0.38545, 0.769005, -0.154455],
        [0.100526, 0.829802, 0.069673],
        [-0.007442, -0.02219, 1.029632],
    ],
    [
        [0.319627, 0.849633, -0.169261],
        [0.106241, 0.815969, 0.07779],
        [-0.007025, -0.028051, 1.035076],
    ],
    [
        [0.259411, 0.923008, -0.18242],
        [0.110296, 0.80434, 0.085364],
        [-0.006276, -0.034346, 1.040622],
    ],
    [
        [0.203876, 0.990338, -0.194214],
        [0.112975, 0.794542, 0.092483],
        [-0.005222, -0.041043, 1.046265],
    ],
    [
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998],
    ],
];

const BRETTEL_DEUTAN_W1: [[f64; 3]; 3] = [
    [2.0757138256610466, 0.0, -21.409141476259606],
    [1.466463363392979, 0.0, 2.3317439563667293],
    [-0.22661490011149105, 0.0, 68.30654343816653],
];

const BRETTEL_DEUTAN_W2: [[f64; 3]; 3] = [
    [2.124834794256137, 0.0, -23.323256212281898],
    [1.4461308480260673, 0.0, 3.124048513815847],
    [-0.2250635463221503, 0.0, 68.24609126806706],
];

const BRETTEL_DEUTAN_SEP: [f64; 3] = [-0.016813516536000002, 0.0, 0.6551784438780001];

const VIENOT_DEUTAN: [[f64; 3]; 3] = [
    [0.2927501142784356, 0.7072498857215644, 1.1102230246251565e-16],
    [0.2927501142784356, 0.7072498857215644, -5.551115123125783e-17],
    [-0.022336587034129083, 0.022336587034129093, 1.0],
];

const MACHADO_DEUTAN: [[[f64; 3]; 3]; 11] = [
    [[1.0, 0.0, -0.0], [0.0, 1.0, 0.0], [-0.0, -0.0, 1.0]],
    [
        [0.866435, 0.177704, -0.044139],
        [0.049567, 0.939063, 0.01137],
        [-0.003453, 0.007233, 0.99622],
    ],
    [
        [0.760729, 0.319078, -0.079807],
        [0.090568, 0.889315, 0.020117],
        [-0.006027, 0.013325, 0.992702],
    ],
    [
        [0.675425, 0.43385, -0.109275],
        [0.125303, 0.847755, 0.026942],
        [-0.00795, 0.018572, 0.989378],
    ],
    [[0.605511, 0.52856, -0.134071], [0.155318, 0.812366, 0.032316], [-0.009376, 0.023176, 0.9862]],
    [
        [0.547494, 0.607765, -0.155259],
        [0.181692, 0.781742, 0.036566],
        [-0.01041, 0.027275, 0.983136],
    ],
    [
        [0.498864, 0.674741, -0.173604],
        [0.205199, 0.754872, 0.039929],
        [-0.011131, 0.030969, 0.980162],
    ],
    [
        [0.457771, 0.731899, -0.18967],
        [0.226409, 0.731012, 0.042579],
        [-0.011595, 0.034333, 0.977261],
    ],
    [
        [0.422823, 0.781057, -0.203881],
        [0.245752, 0.709602, 0.044646],
        [-0.011843, 0.037423, 0.974421],
    ],
    [[0.392952, 0.82361, -0.216562], [0.263559, 0.69021, 0.046232], [-0.01191, 0.040281, 0.97163]],
    [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.01182, 0.04294, 0.968881],
    ],
];

const BRETTEL_TRITAN_W1: [[f64; 3]; 3] = [
    [7.392856536180033, -11.148044821248138, 0.0],
    [-0.34194012421930653, 3.5501661175064, 0.0],
    [-4.2050692716448586, 10.89115898202731, 0.0],
];

const BRETTEL_TRITAN_W2: [[f64; 3]; 3] = [
    [8.0643934576311, -12.42414705871019, 0.0],
    [-0.9956078228581946, 4.7923119863996835, 0.0],
    [-0.2150297288038942, 3.3090019545637928, 0.0],
];

const BRETTEL_TRITAN_SEP: [f64; 3] = [0.344781556122, -0.6551784438780001, 0.0];

const VIENOT_TRITAN: [[f64; 3]; 3] = [
    [1.0000000000000002, 0.1446122433069361, -0.1446122433069363],
    [3.469446951953614e-17, 0.8592358078045899, 0.14076419219541025],
    [-4.163336342344337e-17, 0.8592358078045896, 0.14076419219541023],
];

const MACHADO_TRITAN: [[[f64; 3]; 3]; 11] = [
    [[1.0, 0.0, -0.0], [0.0, 1.0, 0.0], [-0.0, -0.0, 1.0]],
    [[0.92667, 0.092514, -0.019184], [0.021191, 0.964503, 0.014306], [0.008437, 0.054813, 0.93675]],
    [[0.89572, 0.13333, -0.02905], [0.029997, 0.9454, 0.024603], [0.013027, 0.104707, 0.882266]],
    [
        [0.905871, 0.127791, -0.033662],
        [0.026856, 0.941251, 0.031893],
        [0.01341, 0.148296, 0.838294],
    ],
    [
        [0.948035, 0.08949, -0.037526],
        [0.014364, 0.946792, 0.038844],
        [0.010853, 0.193991, 0.795156],
    ],
    [
        [1.017277, 0.027029, -0.044306],
        [-0.006113, 0.958479, 0.047634],
        [0.006379, 0.248708, 0.744913],
    ],
    [
        [1.104996, -0.046633, -0.058363],
        [-0.032137, 0.971635, 0.060503],
        [0.001336, 0.317922, 0.680742],
    ],
    [
        [1.193214, -0.109812, -0.083402],
        [-0.058496, 0.97941, 0.079086],
        [-0.002346, 0.403492, 0.598854],
    ],
    [
        [1.257728, -0.139648, -0.118081],
        [-0.078003, 0.975409, 0.102594],
        [-0.003316, 0.501214, 0.502102],
    ],
    [
        [1.278864, -0.125333, -0.153531],
        [-0.084748, 0.957674, 0.127074],
        [-0.000989, 0.601151, 0.399838],
    ],
    [
        [1.255528, -0.076749, -0.178779],
        [-0.078411, 0.930809, 0.147602],
        [0.004733, 0.691367, 0.3039],
    ],
];

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::convert::oklch_to_oklab;
    use crate::color::testutil::{check_gradients, random_lch};
    use crate::scalar::Dual;

    type D3 = Dual<3>;

    const KINDS: [CvdKind; 3] = [CvdKind::Protan, CvdKind::Deutan, CvdKind::Tritan];
    const METHODS: [CvdMethod; 3] = [CvdMethod::Brettel, CvdMethod::Vienot, CvdMethod::Machado];

    fn vars(x: &[f64; 3]) -> [D3; 3] {
        std::array::from_fn(|i| D3::var(x[i], i))
    }

    /// Wartości wyroczni: `fast.simulate_cvd([0.7, 0.12, 40], typ, metoda, 0.6)` w OKLab.
    #[test]
    fn values_match_oracle() {
        let lab = oklch_to_oklab([0.7, 0.12, 40.0]);
        let want = [
            [0.6721201385196386, 0.03828624615403183, 0.06807706775983975],
            [0.6685511386737341, 0.03096425868707159, 0.06691343203185637],
            [0.6678728299482949, 0.02066508684168442, 0.07062162474675453],
            [0.7022053383240112, 0.032508080158650934, 0.08187546794552872],
            [0.7026021722317514, 0.02031385807066874, 0.0828098885771721],
            [0.70400044934473, 0.01302823418776545, 0.08209888170435618],
            [0.7014941297872345, 0.10895629352015579, 0.045753698034922775],
            [0.7010230398924648, 0.10385671234520784, 0.05516117279006293],
            [0.7020691715793766, 0.11456371449742546, 0.06311143142660823],
        ];
        let mut n = 0;
        for kind in KINDS {
            for method in METHODS {
                let got = simulate_cvd(lab, kind, method, 0.6);
                for k in 0..3 {
                    assert!(
                        (got[k] - want[n][k]).abs() <= 1e-12,
                        "{kind:?} {method:?}: {got:?} zamiast {:?}",
                        want[n]
                    );
                }
                n += 1;
            }
        }
    }

    #[test]
    fn zero_severity_is_identity_and_severity_is_clamped() {
        let lab = oklch_to_oklab([0.6, 0.15, 140.0]);
        for kind in KINDS {
            for method in METHODS {
                let same = simulate_cvd(lab, kind, method, 0.0);
                for k in 0..3 {
                    assert!((same[k] - lab[k]).abs() < 1e-12, "{kind:?} {method:?}");
                }
                assert_eq!(
                    simulate_cvd(lab, kind, method, 3.0),
                    simulate_cvd(lab, kind, method, 1.0)
                );
                assert_eq!(simulate_cvd(lab, kind, method, -1.0), same);
                assert_eq!(simulate_cvd(lab, kind, method, f64::NAN), same);
            }
        }
    }

    #[test]
    fn derivatives_match_finite_differences() {
        let mut seed = 60;
        for kind in KINDS {
            for method in METHODS {
                for severity in [1.0, 0.6] {
                    for k in 0..3 {
                        seed += 1;
                        check_gradients(
                            &format!("simulate_cvd {kind:?} {method:?} {severity} [{k}]"),
                            seed,
                            200,
                            &|rng| oklch_to_oklab(random_lch(rng)),
                            &|x| simulate_cvd(*x, kind, method, severity)[k],
                            &|x| simulate_cvd(vars(x), kind, method, severity)[k].d,
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn degenerate_colors_give_finite_values_and_derivatives() {
        for lab in [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 0.0, 0.0]] {
            for kind in KINDS {
                for method in METHODS {
                    for severity in [1.0, 0.6, 0.0] {
                        for v in simulate_cvd(vars(&lab), kind, method, severity) {
                            assert!(v.v.is_finite(), "{lab:?} {kind:?} {method:?}: {v:?}");
                            assert!(
                                v.d.iter().all(|d| d.is_finite()),
                                "{lab:?} {kind:?} {method:?}: {v:?}"
                            );
                        }
                    }
                }
            }
        }
    }
}
