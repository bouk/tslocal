use crate::types::Node;

impl Node {
    /// Reports whether the node has any ACL tags.
    pub fn is_tagged(&self) -> bool {
        !self.tags.is_empty()
    }
}
