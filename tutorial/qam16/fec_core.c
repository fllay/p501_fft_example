/* Decoders for the FEC study (fec_sim.py): K=7 rate-1/2 soft Viterbi, and the polar code (encoder, successive cancellation with a list, CRC-aided).
   LLR convention: positive = the bit is 0. Min-sum arithmetic (the decisions do not depend on the scale of the LLRs).
   Polar decoder after Tal and Vardy, "List decoding of polar codes": per path the LLR layers P and the partial-sum layers C; a path that has to be split copies its state. */
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ---------------------------------------------------------------- convolutional code, K = 7, polynomials 133 and 171 (octal), start and end in state 0 */
static int parity7(int v) { v ^= v >> 4; v ^= v >> 2; v ^= v >> 1; return v & 1; }

void conv_encode(const unsigned char *u, int n, unsigned char *c)        /* n input bits (the tail of 6 zeros is part of them) -> 2n coded bits */
{
    int sr = 0;
    for (int i = 0; i < n; i++) {
        sr = ((sr << 1) | u[i]) & 0x7F;
        c[2 * i] = parity7(sr & 0133);
        c[2 * i + 1] = parity7(sr & 0171);
    }
}

void viterbi(const float *llr, int n, unsigned char *u)                  /* n trellis steps, 2n LLRs; the last 6 input bits are the zero tail */
{
    float pm[64], npm[64];
    unsigned char *dec = (unsigned char *)malloc((size_t)n * 64);
    int o0[64][2], o1[64][2];
    for (int s = 0; s < 64; s++)
        for (int b = 0; b < 2; b++) {
            int sr = ((s << 1) | b) & 0x7F;                                /* the register after shifting b in: 7 bits, the newest in bit 0 */
            o0[s][b] = parity7(sr & 0133); o1[s][b] = parity7(sr & 0171);
        }
    for (int s = 0; s < 64; s++) pm[s] = -1e30f;
    pm[0] = 0;
    for (int i = 0; i < n; i++) {
        float l0 = llr[2 * i], l1 = llr[2 * i + 1];
        for (int s = 0; s < 64; s++) npm[s] = -1e30f;
        for (int s = 0; s < 64; s++) {
            if (pm[s] < -1e29f) continue;
            for (int b = 0; b < 2; b++) {
                int ns = ((s << 1) | b) & 63;
                float m = pm[s] + 0.5f * ((o0[s][b] ? -l0 : l0) + (o1[s][b] ? -l1 : l1));
                if (m > npm[ns]) { npm[ns] = m; dec[(size_t)i * 64 + ns] = (unsigned char)(s >> 5); }   /* the oldest bit of the predecessor tells which one it was */
            }
        }
        memcpy(pm, npm, sizeof pm);
    }
    int s = 0;                                                             /* terminated: end in state 0 */
    for (int i = n - 1; i >= 0; i--) {
        u[i] = (unsigned char)(s & 1);
        int top = dec[(size_t)i * 64 + s];
        s = (s >> 1) | (top << 5);
    }
    free(dec);
}

/* ---------------------------------------------------------------- polar code */
static inline float fmin_(float a, float b)
{
    float sa = a < 0 ? -1.f : 1.f, sb = b < 0 ? -1.f : 1.f, ma = fabsf(a), mb = fabsf(b);
    return sa * sb * (ma < mb ? ma : mb);
}

typedef struct {
    int m, N;
    float **P;                 /* P[lam], lam = 1..m, size N >> lam (layer 0 is the shared channel vector) */
    unsigned char **C;         /* C[lam], lam = 0..m, size 2 * (N >> lam) */
    float pm;
} Path;

static Path *path_new(int m, int with_c0)
{
    Path *p = (Path *)calloc(1, sizeof(Path));
    p->m = m; p->N = 1 << m;
    p->P = (float **)calloc(m + 1, sizeof(float *));
    p->C = (unsigned char **)calloc(m + 1, sizeof(unsigned char *));
    for (int l = 1; l <= m; l++) p->P[l] = (float *)calloc((size_t)(p->N >> l), sizeof(float));
    for (int l = (with_c0 ? 0 : 1); l <= m; l++) p->C[l] = (unsigned char *)calloc((size_t)2 * (p->N >> l), 1);
    return p;
}
static void path_free(Path *p)
{
    for (int l = 0; l <= p->m; l++) { free(p->P[l]); free(p->C[l]); }
    free(p->P); free(p->C); free(p);
}
static void path_copy(Path *dst, const Path *src)
{
    for (int l = 1; l <= src->m; l++) memcpy(dst->P[l], src->P[l], sizeof(float) * (src->N >> l));
    for (int l = 1; l <= src->m; l++) memcpy(dst->C[l], src->C[l], (size_t)2 * (src->N >> l));
    dst->pm = src->pm;
}

static void calc_p(Path *p, const float *ch, int lam, int phi)
{
    if (lam == 0) return;
    int psi = phi >> 1, n = p->N >> lam;
    const float *prev = (lam == 1) ? ch : p->P[lam - 1];
    if ((phi & 1) == 0) calc_p(p, ch, lam - 1, psi);
    float *cur = p->P[lam];
    if ((phi & 1) == 0)
        for (int b = 0; b < n; b++) cur[b] = fmin_(prev[2 * b], prev[2 * b + 1]);
    else
        for (int b = 0; b < n; b++) { float u = p->C[lam][2 * b] ? -1.f : 1.f; cur[b] = prev[2 * b + 1] + u * prev[2 * b]; }
}

static void update_c(Path *p, int lam, int phi)
{
    int psi = phi >> 1, n = p->N >> lam;
    if (lam - 1 >= 1 || p->C[0]) {
        unsigned char *dst = p->C[lam - 1];
        for (int b = 0; b < n; b++) {
            dst[2 * (2 * b) + (psi & 1)] = p->C[lam][2 * b] ^ p->C[lam][2 * b + 1];
            dst[2 * (2 * b + 1) + (psi & 1)] = p->C[lam][2 * b + 1];
        }
        if ((psi & 1) && lam - 1 >= 1) update_c(p, lam - 1, psi);
    }
}

void polar_encode(const unsigned char *u, int m, unsigned char *x)
{
    Path *p = path_new(m, 1);
    int N = 1 << m;
    for (int phi = 0; phi < N; phi++) {
        p->C[m][phi & 1] = u[phi];
        if (phi & 1) update_c(p, m, phi);
    }
    for (int b = 0; b < N; b++) x[b] = p->C[0][2 * b];
    path_free(p);
}

static unsigned crc16(const unsigned char *bits, int n)                     /* CRC-16-CCITT, init 0xFFFF, over bits (MSB first) */
{
    unsigned c = 0xFFFF;
    for (int i = 0; i < n; i++) {
        unsigned fb = ((c >> 15) & 1) ^ bits[i];
        c = (c << 1) & 0xFFFF;
        if (fb) c ^= 0x1021;
    }
    return c;
}

void crc16_bits(const unsigned char *bits, int n, unsigned char *out16)
{
    unsigned c = crc16(bits, n);
    for (int i = 0; i < 16; i++) out16[i] = (c >> (15 - i)) & 1;
}

/* L = 1 and crc = 0 is plain successive cancellation. frozen[j] = 1: u_j = 0. info_idx: the K non-frozen positions in ascending order; with crc = 1 the last 16 of them carry the CRC of the others.
   u_out: the N decisions of the chosen path. Returns 1 if a path passed the CRC (or crc = 0). */
int polar_scl(const float *ch, int m, const unsigned char *frozen, const int *info_idx, int K, int L, int crc, unsigned char *u_out)
{
    int N = 1 << m;
    Path *path[32]; unsigned char *ubits[32];
    int act[32], nact = 1;                                                     /* slots of the active paths */
    for (int l = 0; l < L; l++) { path[l] = path_new(m, 0); ubits[l] = (unsigned char *)calloc(N, 1); }
    path[0]->pm = 0; act[0] = 0;
    int par[64], bit[64]; float cm[64];
    for (int phi = 0; phi < N; phi++) {
        for (int k = 0; k < nact; k++) calc_p(path[act[k]], ch, m, phi);
        if (frozen[phi]) {
            for (int k = 0; k < nact; k++) {
                Path *p = path[act[k]]; float v = p->P[m][0];
                if (v < 0) p->pm += -v;
                p->C[m][phi & 1] = 0; ubits[act[k]][phi] = 0;
            }
        } else {
            int nc = 0;
            for (int k = 0; k < nact; k++) {
                int sl = act[k]; float v = path[sl]->P[m][0];
                par[nc] = sl; bit[nc] = 0; cm[nc++] = path[sl]->pm + (v < 0 ? -v : 0);
                par[nc] = sl; bit[nc] = 1; cm[nc++] = path[sl]->pm + (v > 0 ? v : 0);
            }
            int keep = nc < L ? nc : L, sel[32], nsel = 0;
            char used[64]; memset(used, 0, sizeof used);
            for (int k = 0; k < keep; k++) {
                int b = -1;
                for (int c = 0; c < nc; c++) if (!used[c] && (b < 0 || cm[c] < cm[b])) b = c;
                used[b] = 1; sel[nsel++] = b;
            }
            int cnt[32]; memset(cnt, 0, sizeof cnt);
            for (int k = 0; k < nsel; k++) cnt[par[sel[k]]]++;
            int freeslot[32], nfree = 0;
            for (int l = 0; l < L; l++) if (cnt[l] == 0) freeslot[nfree++] = l;
            int target[32], first[32]; for (int l = 0; l < 32; l++) first[l] = 0;
            for (int k = 0; k < nsel; k++) {
                int pl = par[sel[k]];
                if (!first[pl]) { first[pl] = 1; target[k] = pl; }
                else { int f = freeslot[--nfree]; path_copy(path[f], path[pl]); memcpy(ubits[f], ubits[pl], N); target[k] = f; }
            }
            for (int k = 0; k < nsel; k++) {
                int t = target[k], b = bit[sel[k]];
                path[t]->pm = cm[sel[k]];
                path[t]->C[m][phi & 1] = (unsigned char)b; ubits[t][phi] = (unsigned char)b;
                act[k] = t;
            }
            nact = nsel;
        }
        if (phi & 1) for (int k = 0; k < nact; k++) update_c(path[act[k]], m, phi);
    }
    int best, ok = 0, order[32];
    for (int k = 0; k < nact; k++) order[k] = act[k];
    for (int i = 0; i < nact; i++) for (int j = i + 1; j < nact; j++) if (path[order[j]]->pm < path[order[i]]->pm) { int t = order[i]; order[i] = order[j]; order[j] = t; }
    best = order[0];
    if (!crc) ok = 1;
    else {
        unsigned char data[8192]; unsigned char chk[16];
        for (int i = 0; i < nact; i++) {
            int l = order[i];
            for (int k = 0; k < K; k++) data[k] = ubits[l][info_idx[k]];
            crc16_bits(data, K - 16, chk);
            if (memcmp(chk, data + K - 16, 16) == 0) { best = l; ok = 1; break; }
        }
    }
    memcpy(u_out, ubits[best], N);
    for (int l = 0; l < L; l++) { path_free(path[l]); free(ubits[l]); }
    return ok;
}
