// Authored bridge to installed public APIs. No model/source assets are vendored.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createInterface } from 'node:readline';
import { once } from 'node:events';

const runtime = process.argv[2];
if (!runtime) throw new Error('installed runtime directory required');
const require = createRequire(`${runtime}/package.json`);
const neural = await import(pathToFileURL(require.resolve('@mailwoman/neural')));
const mailwoman = await import(pathToFileURL(require.resolve('mailwoman')));
const emitter = await import(pathToFileURL(require.resolve('@mailwoman/libpostal/engine')));
const classifier = await neural.NeuralAddressClassifier.loadFromWeights({
  locale: 'en-US', executionProviders: ['cpu'], intraOpNumThreads: 1,
});
const pipeline = mailwoman.createRuntimePipeline({ classifier });
let rows = 0, errors = 0;
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    const input = JSON.parse(line);
    const prediction = {
      schema: 'address-benchmark.prediction/v1', id: input.id,
      input_sha256: input.input_sha256, status: 'ok',
      evidence: [], tokens: [], inferred: [], normalized: [], native: null,
    };
    try {
      const output = await pipeline(input.text);
      const components = emitter.toLibpostalComponents(emitter.treeToParseMatches(output.tree));
      prediction.evidence = components.map(item => ({ native_role: item.label, value: item.value, spans: null }));
      prediction.native = { tree: output.tree, components, normalized: output.normalized };
    } catch (error) {
      prediction.status = 'error';
      prediction.message = `${error.name}: ${error.message}`;
      prediction.native = { error: error.name };
      errors++;
    }
    if (!process.stdout.write(`${JSON.stringify(prediction)}\n`)) await once(process.stdout, 'drain');
    if (++rows % 10000 === 0) process.stderr.write(`rows=${rows} errors=${errors}\n`);
  }
} finally {
  await classifier.dispose?.();
}
