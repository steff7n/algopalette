//! Generator liczb losowych silnika — ALGORYTM ZAMROŻONY.
//!
//! Wynik generowania dla danego ziarna nie może się zmienić po aktualizacji zależności ani
//! kompilatora, więc generator jest własny i mały: SplitMix64 rozwija parę (ziarno, strumień)
//! w stan xoshiro256++. Strumień to numer przebiegu optymalizatora: każdy przebieg ma własny,
//! niezależny ciąg, dzięki czemu wynik nie zależy od liczby wątków.
//!
//! Każda zmiana w tym pliku, która zmienia wartości z testu `frozen_*`, zmienia palety
//! użytkowników dla zapisanych ziaren — nie rób jej.

const GAMMA: u64 = 0x9E37_79B9_7F4A_7C15;
/// Nieparzysty mnożnik rozrzucający numer strumienia po całym słowie (bijekcja mod 2^64).
const STREAM_MUL: u64 = 0xD6E8_FEB8_6659_FD93;

/// Generator xoshiro256++ zasiany przez SplitMix64.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Rng {
    s: [u64; 4],
}

/// Krok SplitMix64: przesuwa stan i zwraca wymieszane słowo.
fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(GAMMA);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Rng {
    /// Generator dla pary (ziarno, strumień).
    ///
    /// Ziarno przechodzi przez jeden krok SplitMix64, wynik jest łączony (xor) z numerem
    /// strumienia pomnożonym przez nieparzystą stałą, a cztery kolejne kroki SplitMix64 od tego
    /// stanu dają stan xoshiro256++.
    pub fn new(seed: u64, stream: u64) -> Self {
        let mut seed_state = seed;
        let mut state = splitmix64(&mut seed_state) ^ stream.wrapping_mul(STREAM_MUL);
        let mut s = [0u64; 4];
        for word in &mut s {
            *word = splitmix64(&mut state);
        }
        if s == [0; 4] {
            // stan zerowy to punkt stały xoshiro; nieosiągalny w praktyce, ale tani do wykluczenia
            s[0] = GAMMA;
        }
        Self { s }
    }

    /// Następne 64 bity (xoshiro256++).
    pub fn next_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let result = s[0].wrapping_add(s[3]).rotate_left(23).wrapping_add(s[0]);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }

    /// Liczba z przedziału [0, 1) o 53 losowych bitach.
    pub fn uniform(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    /// Liczba z przedziału [lo, hi); dla `lo == hi` zwraca `lo`.
    pub fn range(&mut self, lo: f64, hi: f64) -> f64 {
        let x = lo + (hi - lo) * self.uniform();
        // zaokrąglenie może dać dokładnie `hi`; trzymamy przedział półotwarty
        if x >= hi && hi > lo { lo } else { x }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn first4(seed: u64, stream: u64) -> [u64; 4] {
        let mut r = Rng::new(seed, stream);
        [r.next_u64(), r.next_u64(), r.next_u64(), r.next_u64()]
    }

    /// Zamrożenie algorytmu. Wartości policzone niezależną implementacją w Pythonie
    /// (SplitMix64 + xoshiro256++ na liczbach całkowitych dowolnej precyzji).
    #[test]
    fn frozen_first_values_for_seed_1_stream_0() {
        assert_eq!(
            first4(1, 0),
            [
                0x7045_60CE_D7CC_0501,
                0x4EEF_9003_6C89_C53A,
                0xDCE0_5AF2_BA13_64D7,
                0xE019_C821_60DB_BF4C
            ]
        );
    }

    #[test]
    fn frozen_first_values_for_other_seeds_and_streams() {
        assert_eq!(
            first4(1, 1),
            [
                0x74F9_1CAA_4417_C792,
                0xB216_4AA8_25A1_A107,
                0x5F82_791F_58AA_B351,
                0x8D55_04E2_4DF6_CD52
            ]
        );
        assert_eq!(
            first4(0, 0),
            [
                0x84F0_9BF3_07C1_073A,
                0xC82F_FB59_7CEE_E51B,
                0xADF9_6905_C5DF_4417,
                0xE9D9_A848_9D04_2C93
            ]
        );
        assert_eq!(
            first4(u64::MAX, u64::MAX),
            [
                0xA352_742F_3474_292C,
                0x653E_F02E_1054_9CCF,
                0xD8FF_3E2C_9DF0_3511,
                0xD8EF_4E34_6D91_9381
            ]
        );
    }

    /// Wektor wzorcowy xoshiro256++ dla stanu [1, 2, 3, 4] (ten sam co w testach `rand_xoshiro`).
    #[test]
    fn xoshiro256plusplus_reference_vector() {
        let mut r = Rng { s: [1, 2, 3, 4] };
        let got: Vec<u64> = (0..4).map(|_| r.next_u64()).collect();
        assert_eq!(got, [41_943_041, 58_720_359, 3_588_806_011_781_223, 3_591_011_842_654_386]);
    }

    #[test]
    fn uniform_uses_top_53_bits() {
        let mut r = Rng::new(1, 0);
        let got = [r.uniform(), r.uniform(), r.uniform()];
        assert_eq!(got, [0.43855862665058964, 0.3083429344519919, 0.8627983896822804]);
    }

    #[test]
    fn uniform_and_range_stay_in_bounds() {
        let mut r = Rng::new(7, 3);
        for _ in 0..10_000 {
            let u = r.uniform();
            assert!((0.0..1.0).contains(&u));
            let x = r.range(-2.5, 4.0);
            assert!((-2.5..4.0).contains(&x));
        }
        // zakres zdegenerowany zwraca swój jedyny punkt
        assert_eq!(r.range(3.0, 3.0), 3.0);
    }

    #[test]
    fn streams_are_independent_and_reproducible() {
        assert_eq!(first4(42, 5), first4(42, 5));
        assert_ne!(first4(42, 5), first4(42, 6));
        assert_ne!(first4(42, 5), first4(43, 5));
    }
}
