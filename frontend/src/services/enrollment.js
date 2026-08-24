/**
 * @file Enregistrement et restauration des cles cryptographiques du patient.
 */

import {
    evaluatePrf,
    deriveKek,
    generateKeyPair,
    generateSigningKeyPair,
    wrapPrivateKey,
    unwrapPrivateKey,
    exportPublicKey,
    SIGN_ALG,
} from '@/crypto/keys.js'
import { apiGet, apiPost } from './api.js'

/**
 * Genere les DEUX paires de cles de l'utilisateur et les transmet au serveur.
 *
 * Les cles privees sont chiffrees AVANT tout appel reseau : elles ne
 * quittent jamais le navigateur en clair.
 *
 * @returns {Promise<{publicKey: string, signingPublicKey: string}>}
 */
export async function enroll() {
    const prf = await evaluatePrf()
    const kek = await deriveKek(prf)

    const chiffrement = await generateKeyPair()
    const signature = await generateSigningKeyPair()

    const wrappedChiffrement = await wrapPrivateKey(chiffrement.privateKey, kek)
    const wrappedSignature = await wrapPrivateKey(signature.privateKey, kek)

    const publicKey = await exportPublicKey(chiffrement.publicKey)
    const signingPublicKey = await exportPublicKey(signature.publicKey)

    await apiPost('/users/keys', {
        public_key: publicKey,
        encrypted_private_key: wrappedChiffrement.ciphertext,
        private_key_iv: wrappedChiffrement.iv,
        signing_public_key: signingPublicKey,
        encrypted_signing_private_key: wrappedSignature.ciphertext,
        signing_private_key_iv: wrappedSignature.iv,
    })

    return { publicKey, signingPublicKey }
}

/**
 * Recupere les cles de l'utilisateur et dechiffre les deux cles privees.
 *
 * UNE SEULE ceremonie WebAuthn pour les deux : la meme KEK les protege.
 *
 * @returns {Promise<{privateKey: CryptoKey, signingKey: CryptoKey,
 *                    publicKey: string, signingPublicKey: string}>}
 */
export async function restoreKeys() {
    const stored = await apiGet('/users/keys/me')
    const prf = await evaluatePrf()
    const kek = await deriveKek(prf)

    const privateKey = await unwrapPrivateKey(
        { iv: stored.private_key_iv, ciphertext: stored.encrypted_private_key },
        kek,
    )

    const signingKey = await unwrapPrivateKey(
        {
            iv: stored.signing_private_key_iv,
            ciphertext: stored.encrypted_signing_private_key,
        },
        kek,
        SIGN_ALG,
        ['sign'],
    )

    return {
        privateKey,
        signingKey,
        publicKey: stored.public_key,
        signingPublicKey: stored.signing_public_key,
    }
}