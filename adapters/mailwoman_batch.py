"""Whole-file bridge avoids per-address pipe round trips during accuracy runs."""
from address_benchmark.production import NativeBatch
from address_benchmark.ontologies import MAILWOMAN_EMITTER_MAP
from address_benchmark.io import write_json
from concurrent.futures import ThreadPoolExecutor


class Factory(NativeBatch):
    def __init__(self, config):
        super().__init__(config)
        self.metadata['role_map'].update(MAILWOMAN_EMITTER_MAP)
        self.metadata['supported_roles']=sorted({v for v in self.metadata['role_map'].values() if v is not None})
        self.metadata['mapping_version']='mailwoman-emitter-native/v1'
        self.metadata['coordinate_basis']='native tree uses normalized JavaScript text; original UTF-8 fine spans unsupported'
        self.metadata['dependency_versions']=config.get('dependency_versions',{})
        self.metadata['active_roles']=config['active_roles']
        self.metadata['role_inventory_basis']='actual installed English weight model-card BIO labels through the documented native emitter'
        self.workers=config.get('accuracy_workers',1)
        if type(self.workers) is not int or not 1 <= self.workers <= 4:
            raise ValueError('accuracy_workers must be between one and four')
        self.metadata['accuracy_workers']=self.workers
        self.metadata['threading']=f'accuracy only: {self.workers} independent Node processes, one ONNX intra-op thread each; ordered contiguous shards; no timing claim'

    def parse_many(self, requests, directory):
        workers=min(self.workers,len(requests))
        if workers==1:
            yield from NativeBatch.parse_many(self,requests,directory)
            return
        write_json(directory/'shards.json',dict(workers=workers,rows=len(requests),partition='contiguous; preserve original input order',execution='all shards must exit zero; each has its own native execution/log/output artifacts'))
        def execute(index):
            folder=directory/f'shard-{index:02d}'
            folder.mkdir()
            rows=requests[len(requests)*index//workers:len(requests)*(index+1)//workers]
            return list(NativeBatch.parse_many(self,rows,folder))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending=[pool.submit(execute,index) for index in range(workers)]
            for index in range(workers):
                values=pending[index].result()
                yield from values
                pending[index]=None
