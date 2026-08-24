<script>
import { login, handleRedirect } from '@/services/auth.js'
import { enroll, restoreKeys } from '@/services/enrollment.js'
import { apiGet, apiPost } from '@/services/api.js'
import {
  fetchRecord,
  verifyRecord,
  uploadFile,
  downloadFile,
} from '@/services/records.js'

export default {
  name: 'App',

  data() {
    return {
      journal: '',
      utilisateur: null,
      patientSub: null,
      cles: null,
      prenom: 'Jean',
      nom: 'Dupont',
      naissance: '1990-05-14',
      fichierChoisi: null,
      dateExamen: '2026-03-12',
      fichiers: [],
    }
  },

  async mounted() {
    try {
      const claims = await handleRedirect()
      if (claims) {
        this.utilisateur = claims.preferred_username
        this.patientSub = claims.sub
        this.log(`Connecte : ${claims.preferred_username}`)
        this.log(`Groupes  : ${(claims.groups || []).join(', ') || 'aucun'}`)
        this.log('')
      }
    } catch (e) {
      this.log(`ERREUR connexion : ${e.message}`)
    }
  },

  methods: {
    /** @param {string} m */
    log(m) {
      this.journal += m + '\n'
    },

    /** @param {Error} e */
    erreur(e) {
      this.log(`ERREUR : ${e.message}`)
      this.log('')
    },

    seConnecter() {
      login()
    },

    async creerProfil() {
      try {
        await apiPost('/profile', {
          first_name: this.prenom,
          last_name: this.nom,
          date_of_birth: this.naissance,
        })
        this.log('Profil cree.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async voirProfil() {
      try {
        const p = await apiGet('/profile/me')
        this.log(`Profil : ${p.role} - ${p.first_name} ${p.last_name}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async enregistrerCles() {
      try {
        this.log('Generation des deux paires de cles...')
        await enroll()
        this.log('Cles enregistrees sur le serveur.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async deverrouiller() {
      try {
        this.log('Dechiffrement des cles privees...')
        this.cles = await restoreKeys()
        this.log('Cles deverrouillees pour cette session.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {Event} evt */
    choisirFichier(evt) {
      this.fichierChoisi = evt.target.files[0] || null
    },

    async deposer() {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      if (!this.fichierChoisi) return this.log('Choisissez un fichier.\n')
      try {
        this.log(`Chiffrement de "${this.fichierChoisi.name}"...`)
        const r = await uploadFile(
            { file: this.fichierChoisi, examDate: this.dateExamen },
            {
              patientSub: this.patientSub,
              publicKey: this.cles.publicKey,
              signingKey: this.cles.signingKey,
            },
        )
        this.log(`Depose. Identifiant ${r.fileId}, manifeste v${r.version}.`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async lireDossier() {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      try {
        const record = await fetchRecord(this.patientSub)
        this.fichiers = record.files
        this.log(`=== DOSSIER : ${record.files.length} fichier(s) ===`)

        const v = await verifyRecord(record, this.cles.signingPublicKey)
        this.log(v.ok ? `MANIFESTE VALIDE - ${v.raison}` : `ALERTE : ${v.raison}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {string} id */
    async ouvrir(id) {
      try {
        const doc = await downloadFile(id, this.cles.privateKey)
        this.log(`=== ${id} ===`)
        this.log(`Nom   : ${doc.filename}`)
        this.log(`Date  : ${doc.examDate}`)
        this.log(`Poids : ${doc.content.byteLength} octets`)
        this.log(`Debut : ${new TextDecoder().decode(doc.content.slice(0, 60))}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },
  },
}
</script>

<template>
  <main>
    <h1>Hospital Security</h1>
    <p v-if="utilisateur">Utilisateur : <strong>{{ utilisateur }}</strong></p>
    <p v-else>Non connecte.</p>

    <section>
      <button @click="seConnecter" :disabled="!!utilisateur">1. Se connecter</button>
    </section>

    <section v-if="utilisateur">
      <h2>Profil</h2>
      <input v-model="prenom" placeholder="Prenom" />
      <input v-model="nom" placeholder="Nom" />
      <input v-model="naissance" type="date" />
      <button @click="creerProfil">2. Creer mon profil</button>
      <button @click="voirProfil">Voir mon profil</button>
    </section>

    <section v-if="utilisateur">
      <h2>Cles</h2>
      <button @click="enregistrerCles">3. Enregistrer mes cles</button>
      <button @click="deverrouiller">4. Deverrouiller mes cles</button>
    </section>

    <section v-if="cles">
      <h2>Dossier medical</h2>
      <input type="file" @change="choisirFichier" />
      <input v-model="dateExamen" type="date" />
      <button @click="deposer">5. Deposer le fichier</button>
      <button @click="lireDossier">6. Lire mon dossier</button>

      <ul v-if="fichiers.length">
        <li v-for="f in fichiers" :key="f.id">
          {{ f.id }} — {{ f.status }}
          <button @click="ouvrir(f.id)">Ouvrir</button>
        </li>
      </ul>
    </section>

    <pre>{{ journal }}</pre>
  </main>
</template>

<style scoped>
main { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
section { margin: 1.2rem 0; }
h2 { font-size: 1rem; margin-bottom: .4rem; }
button, input { padding: .5rem .8rem; margin: .2rem .2rem .2rem 0; font-size: .95rem; }
button { cursor: pointer; }
li { margin: .3rem 0; font-family: monospace; font-size: .85rem; }
pre { background: #f4f4f4; padding: 1rem; white-space: pre-wrap; word-break: break-all; }
</style>