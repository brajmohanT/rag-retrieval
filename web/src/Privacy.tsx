// What this demo sends where, and how the same pipeline can run inside an organisation's own boundary.
export function Privacy() {
  return (
    <article className="page-article">
      <h2>Data, privacy, and deployment</h2>
      <p className="lede">
        This demo uses public documents and hosted model APIs. An organisation's documents usually cannot be handled the same
        way, so here is what moved where, and what changes for a private deployment.
      </p>

      <h3>What this demo does with data</h3>
      <ul>
        <li>
          <strong>The documents are public.</strong> 14 European Commission reports, all CC BY 4.0, from the ViDoRe V3 HR
          benchmark.
        </li>
        <li>
          <strong>Browsing sends nothing to any model.</strong> Every ranking and answer you see was computed in advance and is
          served from a file.
        </li>
        <li>
          <strong>Building it did call external APIs.</strong> Page images and text went to Superlinked (ColQwen3) and, through
          OpenRouter, to Voyage, Qwen embedding, Cohere reranking, and DeepSeek hosts. OpenRouter spread DeepSeek calls across many
          hosting companies (19 in a sample of 77 calls), which is acceptable for public data and not for confidential data.
        </li>
      </ul>

      <h3>Three ways to deploy for an organisation</h3>
      <div className="cards">
        <section className="card">
          <h4>Managed APIs</h4>
          <p className="small">Fastest to start; what this demo uses.</p>
          <ul className="small">
            <li>Sign data-processing agreements with each provider.</li>
            <li>Pin specific providers and regions; turn off prompt logging and training where offered.</li>
            <li>Suited to non-confidential or already-public material.</li>
          </ul>
        </section>
        <section className="card">
          <h4>Private cloud</h4>
          <p className="small">The same pipeline inside your own cloud account.</p>
          <ul className="small">
            <li>Self-host open-weight models on GPUs: ColQwen3 (Apache-2.0) for page images, an open text-embedding model, keyword search.</li>
            <li>Documents and questions never leave your network boundary.</li>
            <li>Trade-off: GPU costs replace per-call fees, and proprietary rerankers may not be available.</li>
          </ul>
        </section>
        <section className="card">
          <h4>On-premises</h4>
          <p className="small">For data that cannot go to any cloud.</p>
          <ul className="small">
            <li>As private cloud, on your own hardware.</li>
            <li>Plan GPU capacity for indexing peaks; questions need far less.</li>
            <li>Model updates arrive as files you review and install.</li>
          </ul>
        </section>
      </div>

      <h3>What to check before going live</h3>
      <ul>
        <li>
          <strong>Model licences:</strong> confirm each model's licence allows your use; open-weight does not always mean
          commercial use.
        </li>
        <li>
          <strong>Document permissions:</strong> retrieval must respect who may see which document, at query time, not only at
          indexing.
        </li>
        <li>
          <strong>Retention and logging:</strong> decide what questions, answers, and retrieved pages are stored, and for how
          long.
        </li>
        <li>
          <strong>Evidence trail:</strong> keep citations to exact pages, as this demo does, so every answer can be checked.
        </li>
        <li>
          <strong>Your own evaluation:</strong> label a few hundred questions on your documents and rerun this comparison before
          choosing a setup.
        </li>
      </ul>
    </article>
  )
}
