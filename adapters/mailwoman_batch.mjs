// Authored batch bridge to installed Mailwoman public APIs; no vendored assets.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createReadStream, createWriteStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { createHash } from 'node:crypto';
import { once } from 'node:events';

const [runtime, inputs, output] = process.argv.slice(2);
if (!runtime || !inputs || !output) throw new Error('runtime, input-only file, output required');
const require = createRequire(`${runtime}/package.json`);
const { NeuralAddressClassifier } = await import(pathToFileURL(require.resolve('@mailwoman/neural')));
const { createRuntimePipeline } = await import(pathToFileURL(require.resolve('mailwoman')));
const { treeToParseMatches, toLibpostalComponents } = await import(pathToFileURL(require.resolve('@mailwoman/libpostal/engine')));
const classifier = await NeuralAddressClassifier.loadFromWeights({ locale: 'en-US', executionProviders: ['cpu'], intraOpNumThreads: 1 });
const pipeline = createRuntimePipeline({ classifier });
const stream = createWriteStream(output, { flags: 'wx' });
let rows = 0, errors = 0;
try {
  for await (const line of createInterface({ input: createReadStream(inputs), crlfDelay: Infinity })) {
    const request = JSON.parse(line);
    const row = { id: request.id, input_sha256: createHash('sha256').update(request.input).digest('hex'), namespace: 'neutral', labels: [], error: null };
    try {
      const result = await pipeline(request.input);
      row.labels = toLibpostalComponents(treeToParseMatches(result.tree));
      row.native = { tree: result.tree, normalized: result.normalized };
    } catch (error) {
      row.error = `${error.name}: ${error.message}`;
      errors++;
    }
    if (!stream.write(`${JSON.stringify(row)}\n`)) await once(stream, 'drain');
    if (++rows % 10000 === 0) process.stderr.write(`rows=${rows} errors=${errors}\n`);
  }
  stream.end();
  await once(stream, 'finish');
} finally {
  await classifier.dispose?.();
}
