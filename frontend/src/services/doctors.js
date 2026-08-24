/**
 * @file Gestion des medecins autorises par le patient.
 *
 * C'est le coeur du partage : le RECHIFFREMENT. Le patient fabrique dans
 * son navigateur, pour chacun de ses fichiers, une copie de la cle lisible
 * par le medecin choisi.
 *
 *   NAVIGATEUR DU PATIENT                      SERVEUR
 *   ---------------------                      -------
 *   1. je telecharge mon enveloppe   <-------- wrapped_dek (pour moi)
 *   2. je l'ouvre avec ma cle privee
 *   3. je referme le contenu avec la
 *      cle publique du medecin
 *   4. j'envoie la nouvelle enveloppe --------> wrapped_dek (pour le medecin)
 *                                              stockee telle quelle, illisible
 *
 * Le serveur ne peut PAS faire l'etape 2 : il ne possede aucune cle privee.
 * Un administrateur ne peut donc pas s'octroyer l'acces a un dossier.
 */

import { importPublicKey } from '@/crypto/keys.js'
import { rewrapDek } from '@/crypto/files.js'
import { apiGet, apiPost, apiDelete } from './api.js'
import { fetchRecord } from './records.js'

/**
 * Cherche des medecins par nom. Le filtrage est fait par le serveur (ORM).
 * @param {string} [recherche]
 * @returns {Promise<object[]>}
 */
export function listDoctors(recherche = '') {
    const q = recherche ? `?q=${encodeURIComponent(recherche)}` : ''
    return apiGet(`/doctors${q}`)
}

/**
 * Liste les liens de l'utilisateur courant (ses medecins, ou ses patients).
 * @returns {Promise<object[]>}
 */
export function listLinks() {
    return apiGet('/links')
}

/**
 * Re-scelle TOUTES les cles du dossier pour un destinataire.
 *
 * Seuls les fichiers APPROUVES sont traites : un fichier depose par un
 * medecin et pas encore valide par le patient ne fait pas partie du
 * dossier, il n'a donc pas a etre partage.
 *
 * @param {string} publicKeyB64 Cle publique du destinataire.
 * @param {{patientSub: string, privateKey: CryptoKey}} cles Cles du patient.
 * @returns {Promise<{file_id: string, wrapped_dek: string}[]>}
 */
async function rewrapAll(publicKeyB64, { patientSub, privateKey }) {
    if (!publicKeyB64) {
        throw new Error("Ce medecin n'a pas encore enregistre ses cles.")
    }

    const cleDestinataire = await importPublicKey(publicKeyB64)
    const record = await fetchRecord(patientSub)

    const resultat = []
    for (const fichier of record.files) {
        if (fichier.status !== 'approved') continue
        const stored = await apiGet(`/records/files/${fichier.id}`)
        resultat.push({
            file_id: fichier.id,
            wrapped_dek: await rewrapDek(
                stored.wrapped_dek,
                privateKey,
                cleDestinataire,
            ),
        })
    }
    return resultat
}

/**
 * Le patient autorise un medecin : lien approuve + cles partagees, en une
 * seule requete que le serveur traite dans une seule transaction.
 *
 * @param {object} medecin Element de listDoctors().
 * @param {{patientSub: string, privateKey: CryptoKey}} cles
 * @returns {Promise<object>}
 */
export async function addDoctor(medecin, cles) {
    const rewrapped_keys = await rewrapAll(medecin.public_key, cles)
    return apiPost('/links/create', {
        doctor_sub: medecin.keycloak_sub,
        rewrapped_keys,
    })
}

/**
 * Le patient approuve une demande venue d'un medecin.
 *
 * Approbation et partage des cles sont indissociables : approuver sans
 * fournir de cles donnerait un acces vide, fournir des cles sans approuver
 * contournerait le consentement.
 *
 * @param {object} lien Element de listLinks().
 * @param {{patientSub: string, privateKey: CryptoKey}} cles
 * @returns {Promise<object>}
 */
export async function approveDoctor(lien, cles) {
    const rewrapped_keys = await rewrapAll(lien.doctor_public_key, cles)
    return apiPost(`/links/${lien.id}/approve`, { rewrapped_keys })
}

/**
 * Le patient retire un medecin : le lien ET ses cles sont supprimes.
 *
 * LIMITE ASSUMEE : un fichier deja telecharge et dechiffre par le medecin
 * reste en sa possession. Aucun systeme au monde ne peut reprendre une
 * donnee deja livree. Le retrait empeche tout acces FUTUR.
 *
 * @param {number} linkId
 * @returns {Promise<object>}
 */
export function removeDoctor(linkId) {
    return apiDelete(`/links/${linkId}`)
}


/**
 * Cherche des patients par nom. Reserve aux medecins.
 *
 * Le terme de recherche est obligatoire cote serveur : une recherche vide
 * ne renvoie rien, jamais l'annuaire complet.
 *
 * @param {string} recherche
 * @returns {Promise<object[]>}
 */
export function listPatients(recherche) {
    return apiGet(`/patients?q=${encodeURIComponent(recherche || '')}`)
}

/**
 * Un medecin demande l'acces au dossier d'un patient.
 *
 * AUCUNE cle n'est transmise : le medecin ne peut rien re-chiffrer, il ne
 * possede pas les cles du dossier. Le lien reste EN ATTENTE jusqu'a ce que
 * le patient l'approuve et fournisse lui-meme les cles. C'est la traduction
 * technique du consentement : demander n'est pas obtenir.
 *
 * @param {string} patientSub
 * @returns {Promise<object>}
 */
export function requestAccess(patientSub) {
    return apiPost('/links/create', { patient_sub: patientSub })
}