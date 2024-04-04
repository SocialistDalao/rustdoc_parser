use std::fs::File;
use std::io::{self, prelude::*};

use serde::de::value::Error;

pub fn read_json(filename: &str) -> io::Result<serde_json::Value>{
    let mut file  = File::open(filename)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    let json: serde_json::Value = serde_json::from_str(&contents)?;
    return Ok(json);
}

pub fn write_json(filename: &str, json: serde_json::Value) -> io::Result<()> {
    let mut file = File::create(filename)?;
    file.write_all(json.to_string().as_bytes())?;
    return Ok(());
}

mod tests {
    use super::*;

    #[test]
    fn test_read_json() {
        let mut json = read_json("tmp.json").unwrap();
        println!("{:?}", json);
        json["name"] = serde_json::Value::String("Jack".to_string());
        println!("{:?}", json);
        write_json("tmp.json", json).unwrap();
    }

    fn test_all_docs() {
        let mut json = read_json("../all_docs.json").unwrap();

    }
}