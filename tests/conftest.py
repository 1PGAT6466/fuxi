import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope='session')
def test_db_path(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp('test_data')
    return str(db_dir)

@pytest.fixture
def sample_chunks():
    return [
        {
            'file_name': 'test_vlan.md',
            'file_hash': 'abc123',
            'text': 'VLAN 101 peizhi shuoming, duankou GE0/0/13 lianjie AR1, Access moshi.',
            'category': '网络建设',
            'chunk_index': 0
        },
        {
            'file_name': 'guide_mold.pdf',
            'file_hash': 'def456',
            'text': 'moju sheji zhinan: daozhu zhijing D=20, mopei 4040 yixia shiyong A lei jiegou.',
            'category': '模具设计',
            'chunk_index': 0
        },
        {
            'file_name': 'short.txt',
            'file_hash': 'ghi789',
            'text': 'duan',
            'category': '通用办公',
            'chunk_index': 0
        },
    ]
