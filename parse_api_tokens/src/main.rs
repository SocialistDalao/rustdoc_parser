#![feature(rustc_private)]

extern crate rustc_driver;
extern crate rustc_error_codes;
extern crate rustc_errors;
extern crate rustc_hash;
extern crate rustc_hir;
extern crate rustc_interface;
extern crate rustc_session;
extern crate rustc_span;
extern crate rustc_lexer;

use std::{collections::{HashMap, HashSet}, path, process, str, vec};

use rustc_errors::registry;
use rustc_hash::{FxHashMap, FxHashSet};
use rustc_session::config::{self, CheckCfg};
use rustc_span::source_map;
use rustc_lexer::tokenize;

extern crate syn;

use syn::{parse_quote, Item, ItemImpl, ReturnType, Type};
use std::fs::File;
use std::io::prelude::*;
use serde_json::{Value, json};
use anyhow::{Context, Result};

mod json;
use json::{read_json, write_json};

mod api;
use api::{is_api_same, is_api_similar};

use crate::api::parse_api;

fn main() {
    // let input = "fn hello()";
    // for token in tokenize(input) {
    //     println!("{:?}", token);
    // }

    test_single_func_parse();
    // test_parse_compare();

}



/// Things to consider:
/// 1. Name: Impl trait name, function name, impl object name.
/// 2. Generics: Type parameters, lifetime parameters.
/// 3. Inputs: Function inputs.
/// 4. Output: Function output.
/// 
/// Algorithm:
/// 1. Generics are tied with name, inputs and output. 
///     We need to first construct the relation between generics and modifiers, regardless of the name and senquence of declaration.
/// 2. We ignore all WhereClause as it is hard to compare and can crash the comparison.
/// 
/// Implementation:
/// 1. Input: Json files of all plain APIs.
/// 2.1 Parsing: Do the plain parsing of all APIs.
/// 2.2 Detailed Parsing: If no matching API, try to parse the API in detail. Generics and lifetime are taken into consideration.
/// 3. Output: Overwrite the Json files with the detailed parsing.
fn test_single_func_parse() -> Result<()> {
    const MIN_VERSION:usize = 1;
    const MAX_VERSION:usize = 63;
    println!("Start loading APIs...");
    let mut docs = read_json("../all_docs.json").unwrap();
    println!("Start parsing APIs...");
    for i in MIN_VERSION..=MAX_VERSION {
        println!("Start parsing version 1.{}.0 ...", i);
        let index = i - MIN_VERSION;
        let new_doc = docs[index+1].clone();
        for(submodule_path, plain_submodule) in docs[index].as_object_mut().unwrap() {
            // println!("{:?}", submodule_path);
            // println!("{:?}", plain_submodule);
            if i == MAX_VERSION{
                continue;
            }
            if new_doc.get(submodule_path) == None {
                continue;
            }
            // Compare APIs with new version.
            // We first directly compare in string level for performance.
            // The rest are compared in detail (with rustc parser).
            let api_list = plain_submodule["plain_apis"].as_array_mut().context("No plain_apis")?;
            let new_api_list = new_doc[submodule_path]["plain_apis"].as_array().context("No plain_apis")?;
            for api in api_list{
                for (idx , new_api) in new_api_list.iter().enumerate(){
                    if api["next_api_index"] != -1 && is_api_same(api, new_api){
                        api["next_api_index"] = json!(idx as i64);
                        break;
                    }
                }
                if api["next_api_index"] == -1 {
                    for (idx , new_api) in new_api_list.iter().enumerate(){
                        if is_api_similar(api, new_api) {
                            api["next_api_index"] = json!(idx as i64);
                        }
                    }
                }
            }
            // Debug
            let api_list = plain_submodule["plain_apis"].as_array_mut().context("No plain_apis")?;
            let new_api_list = new_doc[submodule_path]["plain_apis"].as_array().context("No plain_apis")?;
            debug_removed_new_api_info(i, api_list, new_api_list);
        }
    }
    Ok(())
}


fn print_api(api: &Value) -> String {
    format!("Submodule:{}, impl:{}, api:{}, extra:{}", api["submodule"], api["impl"], api["api"], api["api"].as_str().unwrap().chars().next().unwrap())
}


fn debug_parsing_api_info(api: &Value){
    let impl_ = api["impl"].as_str().unwrap();
    let api_ = api["api"].as_str().unwrap();
    println!("Impl:{}", impl_);
    println!("Impl Parsing: {:?}", parse_api(impl_));
    println!("API:{}", api_);
    println!("API Parsing: {:?}", parse_api(api_));
}


fn debug_all_apis_info(version_num :usize, api_list: &Vec<Value>){
    for api in api_list{
        println!("Version {:>3} API: {}", version_num, print_api(api));
    }
}


fn debug_removed_new_api_info(version_num :usize, api_list: &Vec<Value>, new_api_list: &Vec<Value>){
    let mut index_set = HashSet::new();
    for api in api_list{
        if api["next_api_index"] == -1 {
            println!("Version {:>3} Removed API: {}", version_num, print_api(api));
        }
        else{
            index_set.insert(api["next_api_index"].as_i64().unwrap() as usize);
        }
    }
    for (idx, new_api) in new_api_list.iter().enumerate(){
        if !index_set.contains(&idx){
            println!("Version {:>3} New API: {}", version_num, print_api(new_api));
        }
    }
}


mod tests {
    use std::io;

    use anyhow::Ok;
    use serde::de::value::Error;
    use serde_json::json;

    use crate::api::{compare_api, parse_api};

    use super::*;

    #[test]
    fn test_parse_one_submodule() -> Result<()> {
        const VERSION:usize = 1;
        let submodule_path = "collections::fmt::RadixFmt";
        let mut docs = read_json("../all_docs.json").unwrap();
        // write_json("./tmp_doc.json", &docs[0..1])?;

        let new_doc = docs[VERSION].clone();
        let plain_submodule: &mut Value = &mut docs[VERSION-1][submodule_path];
        if new_doc.get(submodule_path) == None {
            return Ok(());
        }
        // Compare APIs with new version.
        // We first directly compare in string level for performance.
        // The rest are compared in detail (with rustc parser).
        let api_list = plain_submodule["plain_apis"].as_array_mut().context("No plain_apis")?;
        let new_api_list = new_doc[submodule_path]["plain_apis"].as_array().context("No plain_apis")?;
        debug_parsing_api_info(&api_list[2]);
        debug_parsing_api_info(&new_api_list[2]);
        println!("Same? {}", is_api_similar(&api_list[2], &new_api_list[2]));
        for api in api_list{
            // for (idx , new_api) in new_api_list.iter().enumerate(){
            //     if api["next_api_index"] == -1 && is_api_same(api, new_api){
            //         api["next_api_index"] = json!(idx as i64);
            //         break;
            //     }
            //     println!("Simple Compare Failure: \n\t{:?} with \n\t{:?}", print_api(api), print_api(new_api));
            // }
            if api["next_api_index"] != -1 {
                continue;
            }
            for (idx , new_api) in new_api_list.iter().enumerate(){
                if is_api_similar(api, new_api) {
                    println!("Complex Compare Success: \n\t{:?} with \n\t{:?}", print_api(api), print_api(new_api));
                    api["next_api_index"] = json!(idx as i64);
                    break;
                }
            }
            // let impl_ = api["impl"].as_str().unwrap();
            // let api_ = api["api"].as_str().unwrap();
            // println!("Impl:{}", impl_);
            // println!("Impl Parsing: {:?}", parse_api(impl_));
            // println!("API:{}", api_);
            // println!("API Parsing: {:?}", parse_api(api_));
        }
        // Debug
        let api_list = plain_submodule["plain_apis"].as_array_mut().context("No plain_apis")?;
        let new_api_list = new_doc[submodule_path]["plain_apis"].as_array().context("No plain_apis")?;
        // All APIs
        debug_all_apis_info(VERSION, api_list);
        debug_all_apis_info(VERSION+1, new_api_list);
        // Removed & New API
        debug_removed_new_api_info(VERSION, api_list, new_api_list);

        Ok(())
    }

    #[test]
    fn test_all_docs() -> Result<()> {
        const MIN_VERSION:usize = 1;
        const MAX_VERSION:usize = 3;

        let mut docs = read_json("../all_docs.json").unwrap();
        write_json("./tmp_doc.json", &docs[10])?;
        for i in MIN_VERSION..=MAX_VERSION {
            let index = i - MIN_VERSION;
            let new_doc = docs[index+1].clone();
            for(submodule_path, plain_submodule) in docs[index].as_object_mut().unwrap() {
                println!("{:?}", submodule_path);
                println!("{:?}", plain_submodule);
                if i == MAX_VERSION{
                    continue;
                }
                if new_doc.get(submodule_path) == None {
                    continue;
                }
                // Compare APIs with new version.
                // We first directly compare in string level for performance.
                // The rest are compared in detail (with rustc parser).
                let api_list = plain_submodule["plain_apis"].as_array_mut().context("No plain_apis")?;
                let new_api_list = new_doc[submodule_path]["plain_apis"].as_array().context("No plain_apis")?;
                for api in api_list{
                    for (idx , new_api) in new_api_list.iter().enumerate(){
                        if api["next_api_index"] != -1 && is_api_same(api, new_api){
                            api["next_api_index"] = json!(idx as i64);
                            break;
                        }
                    }
                    if api["next_api_index"] == -1 {
                        for (idx , new_api) in new_api_list.iter().enumerate(){
                            if is_api_similar(api, new_api) {
                                api["next_api_index"] = json!(idx as i64);
                            }
                        }
                    }
                    if api["next_api_index"] == -1 {
                        println!("No matching API: {:?}", api);
                    }
                }
            }
        }

        Ok(())
        
    }


    #[test]
    fn test_full_parse(){
        let out = process::Command::new("rustc")
            .arg("--print=sysroot")
            .current_dir(".")
            .output()
            .unwrap();
        let sysroot = str::from_utf8(&out.stdout).unwrap().trim();
        let config = rustc_interface::Config {
            // Command line options
            opts: config::Options {
                maybe_sysroot: Some(path::PathBuf::from(sysroot)),
                ..config::Options::default()
            },
            // cfg! configuration in addition to the default ones
            crate_cfg: FxHashSet::default(), // FxHashSet<(String, Option<String>)>
            crate_check_cfg: CheckCfg::default(), // CheckCfg
            input: config::Input::Str {
                name: source_map::FileName::Custom("main.rs".into()),
                input: r#"
                fn intersperse(self, separator: Self::Item) -> Intersperse<Self> where Self::Item: Clone;"#
                .into(),
            },
            output_dir: None,  // Option<PathBuf>
            output_file: None, // Option<PathBuf>
            file_loader: None, // Option<Box<dyn FileLoader + Send + Sync>>
            locale_resources: rustc_driver::DEFAULT_LOCALE_RESOURCES,
            lint_caps: FxHashMap::default(), // FxHashMap<lint::LintId, lint::Level>
            // This is a callback from the driver that is called when [`ParseSess`] is created.
            parse_sess_created: None, //Option<Box<dyn FnOnce(&mut ParseSess) + Send>>
            // This is a callback from the driver that is called when we're registering lints;
            // it is called during plugin registration when we have the LintStore in a non-shared state.
            //
            // Note that if you find a Some here you probably want to call that function in the new
            // function being registered.
            register_lints: None, // Option<Box<dyn Fn(&Session, &mut LintStore) + Send + Sync>>
            // This is a callback from the driver that is called just after we have populated
            // the list of queries.
            //
            // The second parameter is local providers and the third parameter is external providers.
            override_queries: None, // Option<fn(&Session, &mut ty::query::Providers<'_>, &mut ty::query::Providers<'_>)>
            // Registry of diagnostics codes.
            registry: registry::Registry::new(&rustc_error_codes::DIAGNOSTICS),
            make_codegen_backend: None,
        };
        rustc_interface::run_compiler(config, |compiler| {
            compiler.enter(|queries| {
                // Parse the program and print the syntax tree.
                let parse = queries.parse().unwrap().get_mut().clone();
                println!("{parse:#?}");
                // Analyze the program and inspect the types of definitions.
                queries.global_ctxt().unwrap().enter(|tcx| {
                    for id in tcx.hir().items() {
                        let hir = tcx.hir();
                        let item = hir.item(id);
                        match item.kind {
                            rustc_hir::ItemKind::Static(_, _, _) | rustc_hir::ItemKind::Fn(_, _, _) => {
                                let name = item.ident;
                                let ty = tcx.type_of(item.hir_id().owner.def_id);
                                println!("{name:?}:\t{ty:?}")
                            }
                            _ => (),
                        }
                    }
                })
            });
        });
    }

    #[test]
    fn test_num(){
        print!("!!{:>5}!!", 1);
    }
}