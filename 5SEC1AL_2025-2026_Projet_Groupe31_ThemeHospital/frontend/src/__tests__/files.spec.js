// @vitest-environment node
import { describe, it, expect } from 'vitest'
import {
    generateKeyPair,
    generateSigningKeyPair,
    signBytes,
    verifyBytes,
    exportPublicKey,
    importPublicKey,
    SIGN_ALG,
} from '../crypto/keys.js'
import {
    generateDek,
    encryptDocument,
    decryptDocument,
    wrapDek,
    unwrapDek,
} from '../crypto/files.js'

const DOC = {
    filename: 'radiographie_thorax.pdf',
    examDate: '2026-03-12',
    content: new TextEncoder().encode('%PDF-1.7 contenu medical').buffer,
}

describe('chiffrement en enveloppe', () => {
    it('restitue le nom, la date et le contenu', async () => {
        const dek = await generateDek()
        const blob = await encryptDocument(DOC, dek)
        const clair = await decryptDocument(blob, dek)

        expect(clair.filename).toBe(DOC.filename)
        expect(clair.examDate).toBe(DOC.examDate)
        expect(new TextDecoder().decode(clair.content)).toBe('%PDF-1.7 contenu medical')
    })

    it('ne laisse fuir ni le nom du fichier ni la date', async () => {
        const dek = await generateDek()
        const blob = await encryptDocument(DOC, dek)

        expect(blob.ciphertext).not.toContain('radiographie')
        expect(blob.ciphertext).not.toContain('2026')
    })

    it('detecte l alteration du bloc chiffre', async () => {
        const dek = await generateDek()
        const blob = await encryptDocument(DOC, dek)

        const altere = blob.ciphertext[0] === 'A' ? 'B' : 'A'
        const falsifie = { ...blob, ciphertext: altere + blob.ciphertext.slice(1) }

        await expect(decryptDocument(falsifie, dek)).rejects.toThrow()
    })

    it('partage la DEK via RSA sans dupliquer le fichier', async () => {
        const dek = await generateDek()
        const blob = await encryptDocument(DOC, dek)

        const patient = await generateKeyPair()
        const medecin = await generateKeyPair()

        const pourPatient = await wrapDek(dek, patient.publicKey)
        const pourMedecin = await wrapDek(dek, medecin.publicKey)

        const dekMedecin = await unwrapDek(pourMedecin, medecin.privateKey)
        const clair = await decryptDocument(blob, dekMedecin)

        expect(clair.filename).toBe(DOC.filename)
        expect(pourPatient).not.toBe(pourMedecin) // deux chiffres differents
    }, 30000)

    it('refuse la DEK d un tiers non autorise', async () => {
        const dek = await generateDek()
        const patient = await generateKeyPair()
        const intrus = await generateKeyPair()

        const pourPatient = await wrapDek(dek, patient.publicKey)

        await expect(unwrapDek(pourPatient, intrus.privateKey)).rejects.toThrow()
    }, 30000)
})

describe('manifeste signe', () => {
    const manifeste = JSON.stringify({
        version: 3,
        files: ['a1b2c3d4-0000-4000-8000-000000000001'],
    })

    it('valide une signature authentique', async () => {
        const paire = await generateSigningKeyPair()
        const data = new TextEncoder().encode(manifeste)

        const sig = await signBytes(data, paire.privateKey)
        const publique = await importPublicKey(
            await exportPublicKey(paire.publicKey),
            SIGN_ALG,
            ['verify'],
        )

        expect(await verifyBytes(data, sig, publique)).toBe(true)
    }, 30000)

    it('DETECTE un fichier retire du manifeste', async () => {
        const paire = await generateSigningKeyPair()
        const sig = await signBytes(new TextEncoder().encode(manifeste), paire.privateKey)

        const falsifie = JSON.stringify({ version: 3, files: [] })
        const publique = await importPublicKey(
            await exportPublicKey(paire.publicKey),
            SIGN_ALG,
            ['verify'],
        )

        expect(
            await verifyBytes(new TextEncoder().encode(falsifie), sig, publique),
        ).toBe(false)
    }, 30000)
})