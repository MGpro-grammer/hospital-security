// @vitest-environment node
// jsdom ne fournit pas crypto.subtle ; l'environnement Node, si.

import { describe, it, expect } from 'vitest'
import {
    bufToB64,
    b64ToBuf,
    deriveKek,
    generateKeyPair,
    wrapPrivateKey,
    unwrapPrivateKey,
    exportPublicKey,
    importPublicKey,
} from '@/crypto/keys.js'

const PRF_A = new Uint8Array([
    0x3e, 0x7b, 0x0b, 0x1e, 0x8c, 0x1d, 0x52, 0xb6, 0x95, 0x60, 0x20, 0xe2, 0x4f, 0x0b, 0x18, 0x2b,
    0x8e, 0xe2, 0x14, 0xcd, 0x2a, 0xaf, 0x44, 0x49, 0x3d, 0x5a, 0x97, 0xce, 0x16, 0x7c, 0x35, 0x19,
])
const PRF_B = new Uint8Array(32).fill(0xab)

describe('encodage base64', () => {
    it('fait un aller-retour sans perte', () => {
        const src = new Uint8Array([0, 1, 250, 255, 128])
        expect(new Uint8Array(b64ToBuf(bufToB64(src)))).toEqual(src)
    })
})

describe('derivation de la KEK', () => {
    it('produit la MEME cle pour une meme sortie PRF', async () => {
        const kek1 = await deriveKek(PRF_A)
        const kek2 = await deriveKek(PRF_A)

        const iv = crypto.getRandomValues(new Uint8Array(12))
        const msg = new TextEncoder().encode('donnee sensible')
        const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, kek1, msg)
        const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, kek2, ct)

        expect(new TextDecoder().decode(pt)).toBe('donnee sensible')
    })

    it('produit une cle DIFFERENTE pour une autre sortie PRF', async () => {
        const kek = await deriveKek(PRF_A)
        const autre = await deriveKek(PRF_B)

        const iv = crypto.getRandomValues(new Uint8Array(12))
        const ct = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv },
            kek,
            new TextEncoder().encode('donnee sensible'),
        )

        await expect(
            crypto.subtle.decrypt({ name: 'AES-GCM', iv }, autre, ct),
        ).rejects.toThrow()
    })
})

describe('cycle complet de la cle privee', () => {
    it('chiffre, dechiffre et reste utilisable', async () => {
        const kek = await deriveKek(PRF_A)
        const paire = await generateKeyPair()

        const wrapped = await wrapPrivateKey(paire.privateKey, kek)
        const restauree = await unwrapPrivateKey(wrapped, kek)

        const publique = await importPublicKey(await exportPublicKey(paire.publicKey))
        const secret = new TextEncoder().encode('resultat analyse')

        const ct = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, publique, secret)
        const pt = await crypto.subtle.decrypt({ name: 'RSA-OAEP' }, restauree, ct)

        expect(new TextDecoder().decode(pt)).toBe('resultat analyse')
    }, 20000)

    it('refuse de dechiffrer la cle privee avec une mauvaise KEK', async () => {
        const kek = await deriveKek(PRF_A)
        const mauvaise = await deriveKek(PRF_B)
        const paire = await generateKeyPair()
        const wrapped = await wrapPrivateKey(paire.privateKey, kek)

        await expect(unwrapPrivateKey(wrapped, mauvaise)).rejects.toThrow()
    }, 20000)

    it('ne laisse aucune trace de la cle privee en clair', async () => {
        const kek = await deriveKek(PRF_A)
        const paire = await generateKeyPair()
        const wrapped = await wrapPrivateKey(paire.privateKey, kek)

        // Une cle PKCS8 en clair commence par 0x30 0x82, soit "MII" en base64.
        expect(wrapped.ciphertext.startsWith('MII')).toBe(false)
    }, 20000)
})