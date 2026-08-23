/**
 * @file Enregistrement et restauration des cles cryptographiques du patient.
 */

import {
    evaluatePrf,
    deriveKek,
    generateKeyPair,
    wrapPrivateKey,
    unwrapPrivateKey,
    exportPublicKey,
} from '@/crypto/keys.js'
import { apiGet, apiPost } from './api.js'

/**
 * Genere la paire de cles de l'utilisateur et la transmet au serveur.
 *
 * La cle privee est chiffree AVANT tout appel reseau : elle ne quitte
 * jamais le navigateur en clair.
 *
 * @returns {Promise<{publicKey: string}>}
 */
export async function enroll() {
    const prf = await evaluatePrf()
    const kek = await deriveKek(prf)
    const pair = await generateKeyPair()
    const wrapped = await wrapPrivateKey(pair.privateKey, kek)
    const publicKey = await exportPublicKey(pair.publicKey)

    await apiPost('/users/keys', {
        public_key: publicKey,
        encrypted_private_key: wrapped.ciphertext,
        private_key_iv: wrapped.iv,
    })

    return { publicKey }
}

/**
 * Recupere la cle privee chiffree depuis le serveur et la dechiffre
 * localement en rederivant la KEK depuis l'authentificateur.
 *
 * @returns {Promise<CryptoKey>} Cle privee utilisable, non extractible.
 */
export async function restorePrivateKey() {
    const stored = await apiGet('/users/keys/me')
    const prf = await evaluatePrf()
    const kek = await deriveKek(prf)

    return unwrapPrivateKey(
        { iv: stored.private_key_iv, ciphertext: stored.encrypted_private_key },
        kek,
    )
}